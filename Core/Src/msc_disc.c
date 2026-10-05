/*
 * The MIT License (MIT)
 *
 * Copyright (c) 2019 Ha Thach (tinyusb.org)
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 *
 */
#include "main.h"
#include "tusb.h"
#include "msc_disc.h"
#include "qspi.h"
#include "ff.h"

#if CFG_TUD_MSC

// whether host does safe-eject
static bool ejected = false;

static msc_state_e disk_state = MSC_STATE_UNKNOWN;

// Adresse im Flash zu (lba, offset). Gibt UINT32_MAX zurueck, wenn der
// Zugriff die Disk oder die Page verlaesst.
static uint32_t msc_addr(uint32_t lba, uint32_t offset, uint32_t bufsize) {
    if (lba >= MSC_BLOCK_COUNT) return UINT32_MAX;
    // CMD_WRITE_PAGE arbeitet page-weise, ein Transfer darf die Page Grenze
    // nicht ueberschreiten.
    if (offset + bufsize > MSC_BLOCK_SIZE) return UINT32_MAX;
    return MSC_RESERVED + lba * MSC_BLOCK_SIZE + offset;
}

// Anzahl Bytes des laufenden asynchronen Transfers. Nur eine Operation ist
// gleichzeitig unterwegs, darum reicht eine einzelne Variable.
static volatile uint32_t pending_bytes = 0;

// Laeuft im QUADSPI bzw. DMA IRQ, darum in_isr = true.
static void msc_io_done(bool ok) {
    tud_msc_async_io_done(ok ? (int32_t)pending_bytes : TUD_MSC_RET_ERROR, true);
}

// FatFs Arbeitsobjekte. Nur beim Start benutzt, aber f_mount() verlangt, dass
// das FATFS Objekt gueltig bleibt solange gemountet ist.
static FATFS fs;
static BYTE  work[FF_MAX_SS];

// Muss vor tusb_init() laufen, damit der Host beim ersten READ10 schon ein
// gueltiges Dateisystem sieht. Gibt hier nichts aus - die Konsole ist zu
// diesem Zeitpunkt noch nicht initialisiert, das Ergebnis holt "msc".
void msc_disk_init(void) {
    // opt = 1: sofort mounten statt beim ersten Zugriff, sonst faende
    // f_mount() ein fehlendes Dateisystem gar nicht.
    FRESULT res = f_mount(&fs, "", 1);
    if (res == FR_OK) {
        disk_state = MSC_STATE_MOUNTED;
        f_mount(NULL, "", 0); // wieder freigeben, ab jetzt gehoert der Traeger dem Host
        return;
    }
    if (res != FR_NO_FILESYSTEM) {
        disk_state = MSC_STATE_READ_ERROR;
        return;
    }

    // Leerer Flash. FM_SFD legt einen blanken Datentraeger ohne
    // Partitionstabelle an - bei 2 MB ist ein MBR nur Ballast.
    // 4 KB Cluster decken sich mit dem Erase Sektor des M95P16 und halten die
    // Clusterzahl weit unter der FAT12 Grenze von 4084.
    const MKFS_PARM opt = {
        .fmt     = FM_FAT | FM_SFD,
        .n_fat   = 1,
        .align   = 1,
        .n_root  = 16,
        .au_size = 8 * MSC_BLOCK_SIZE,
    };
    if (f_mkfs("", &opt, work, sizeof(work)) != FR_OK) {
        disk_state = MSC_STATE_FORMAT_ERROR;
        return;
    }
    if (f_mount(&fs, "", 1) != FR_OK) {
        disk_state = MSC_STATE_FORMAT_ERROR;
        return;
    }
    f_setlabel("RADIOBELL");
    f_mount(NULL, "", 0);
    disk_state = MSC_STATE_FORMATTED;
}

msc_state_e msc_get_state(void) {
    return disk_state;
}

void msc_print_info(void) {
    static const char *state_str[] = {
        [MSC_STATE_UNKNOWN]      = "nicht initialisiert",
        [MSC_STATE_MOUNTED]      = "FAT vorhanden",
        [MSC_STATE_FORMATTED]    = "war leer, FAT12 angelegt",
        [MSC_STATE_READ_ERROR]   = "Flash nicht lesbar",
        [MSC_STATE_FORMAT_ERROR] = "Formatieren fehlgeschlagen",
    };
    printf("MSC state            = %s" NL, state_str[disk_state]);
    printf("MSC blocks           = %lu x %lu B" NL,
           (unsigned long)MSC_BLOCK_COUNT, (unsigned long)MSC_BLOCK_SIZE);
    printf("MSC flash offset     = 0x%06lx" NL, (unsigned long)MSC_RESERVED);
}

// Invoked when received SCSI_CMD_INQUIRY, v2 with full inquiry response
// Some inquiry_resp's fields are already filled with default values, application can update them
// Return length of inquiry response, typically sizeof(scsi_inquiry_resp_t) (36 bytes), can be longer if included vendor data.
uint32_t tud_msc_inquiry2_cb(uint8_t lun, scsi_inquiry_resp_t *inquiry_resp, uint32_t bufsize) {
  (void) lun;
  (void) bufsize;
  const char vid[] = "RadioBel";
  const char pid[] = "M95P16 Flash";
  const char rev[] = "1.0";

  (void) strncpy((char*) inquiry_resp->vendor_id, vid, 8);
  (void) strncpy((char*) inquiry_resp->product_id, pid, 16);
  (void) strncpy((char*) inquiry_resp->product_rev, rev, 4);

  return sizeof(scsi_inquiry_resp_t); // 36 bytes
}

// Invoked when received Test Unit Ready command.
// return true allowing host to read/write this LUN e.g SD card inserted
bool tud_msc_test_unit_ready_cb(uint8_t lun) {
  (void) lun;
  if (!msystem.usb_active){
      return false;
  }
  // RAM disk is ready until ejected
  if (ejected) {
    // Additional Sense 3A-00 is NOT_FOUND
    return tud_msc_set_sense(lun, SCSI_SENSE_NOT_READY, 0x3a, 0x00);
  }

  return true;
}

// Invoked when received SCSI_CMD_READ_CAPACITY_10 and SCSI_CMD_READ_FORMAT_CAPACITY to determine the disk size
// Application update block count and block size
void tud_msc_capacity_cb(uint8_t lun, uint32_t *block_count, uint16_t *block_size) {
  (void) lun;
  *block_count = MSC_BLOCK_COUNT;
  *block_size = MSC_BLOCK_SIZE;
}

// Invoked when received Start Stop Unit command
// - Start = 0 : stopped power mode, if load_eject = 1 : unload disk storage
// - Start = 1 : active mode, if load_eject = 1 : load disk storage
bool tud_msc_start_stop_cb(uint8_t lun, uint8_t power_condition, bool start, bool load_eject) {
  (void) lun;
  (void) power_condition;

  if (load_eject) {
    if (start) {
      // load disk storage
    } else {
      // unload disk storage
      ejected = true;
    }
  }

  return true;
}

// Callback invoked when received READ10 command.
// Copy disk's data to buffer (up to bufsize) and return number of copied bytes.
int32_t tud_msc_read10_cb(uint8_t lun, uint32_t lba, uint32_t offset, void *buffer, uint32_t bufsize) {
  (void) lun;

  uint32_t addr = msc_addr(lba, offset, bufsize);
  if (addr == UINT32_MAX) {
    return TUD_MSC_RET_ERROR;
  }
  if (qspi_is_busy()) {
    return TUD_MSC_RET_BUSY; // tinyUSB fragt spaeter mit denselben Parametern nochmal
  }
  pending_bytes = bufsize;
  if (qspi_read_async((uint8_t *) buffer, addr, bufsize, msc_io_done) != HAL_OK) {
    return TUD_MSC_RET_ERROR;
  }

  return TUD_MSC_RET_ASYNC;
}

bool tud_msc_is_writable_cb(uint8_t lun) {
  (void) lun;

  #ifdef CFG_EXAMPLE_MSC_READONLY
  return false;
  #else
  return true;
  #endif
}

// Callback invoked when received WRITE10 command.
// Process data in buffer to disk's storage and return number of written bytes
int32_t tud_msc_write10_cb(uint8_t lun, uint32_t lba, uint32_t offset, uint8_t *buffer, uint32_t bufsize) {
  (void) lun;

  uint32_t addr = msc_addr(lba, offset, bufsize);
  if (addr == UINT32_MAX) {
    return TUD_MSC_RET_ERROR;
  }
  if (qspi_is_busy()) {
    return TUD_MSC_RET_BUSY;
  }
  // CMD_WRITE_PAGE (0x02) loescht die Page intern, ein separates Erase
  // entfaellt. Der Abschluss kommt per Callback, siehe msc_io_done().
  pending_bytes = bufsize;
  if (qspi_write_async(buffer, addr, bufsize, msc_io_done) != HAL_OK) {
    return TUD_MSC_RET_ERROR;
  }

  return TUD_MSC_RET_ASYNC;
}

// Callback invoked when received an SCSI command not in built-in list below
// - READ_CAPACITY10, READ_FORMAT_CAPACITY, INQUIRY, MODE_SENSE6, REQUEST_SENSE
// - READ10 and WRITE10 has their own callbacks
int32_t tud_msc_scsi_cb(uint8_t lun, uint8_t const scsi_cmd[16], void *buffer, uint16_t bufsize) {
  (void) lun;
  (void) scsi_cmd;
  (void) buffer;
  (void) bufsize;

  // currently no other commands are supported

  // Set Sense = Invalid Command Operation
  (void) tud_msc_set_sense(lun, SCSI_SENSE_ILLEGAL_REQUEST, 0x20, 0x00);

  return -1; // stall/failed command request;
}

#endif
