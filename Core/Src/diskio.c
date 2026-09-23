/*
 * diskio.c
 *
 * Anbindung von FatFs an den M95P16 QSPI Flash.
 *
 * Ersetzt das Beispiel lib/fatfs/source/diskio.c - jenes darf nicht mit
 * uebersetzt werden, sonst kollidieren die Symbole.
 *
 * Es gibt genau ein Volume (FF_VOLUMES = 1) auf pdrv 0. Der Sektor 0 von FatFs
 * liegt bei MSC_RESERVED im Flash, siehe msc_disc.h - dieselbe Abbildung
 * benutzt der USB MSC Pfad in msc_disc.c.
 *
 * Bewusst die synchronen qspi_read()/qspi_write(): FatFs wird nur beim Start
 * benutzt, vor tusb_init(), wenn noch kein asynchroner Transfer laufen kann.
 */
#include "main.h"
#include "ff.h"
#include "diskio.h"
#include "qspi.h"
#include "msc_disc.h"

DSTATUS disk_status(BYTE pdrv) {
    return (pdrv == 0) ? 0 : STA_NOINIT;
}

DSTATUS disk_initialize(BYTE pdrv) {
    // Der QSPI ist zu diesem Zeitpunkt von MX_QUADSPI_Init() aufgesetzt.
    return (pdrv == 0) ? 0 : STA_NOINIT;
}

DRESULT disk_read(BYTE pdrv, BYTE *buff, LBA_t sector, UINT count) {
    if (pdrv != 0) return RES_PARERR;
    if (sector + count > MSC_BLOCK_COUNT) return RES_PARERR;

    // CMD_READ_DATA zaehlt die Adresse ueber Page Grenzen hinweg weiter,
    // ein einziger Transfer genuegt.
    uint32_t addr = MSC_RESERVED + (uint32_t)sector * MSC_BLOCK_SIZE;
    if (qspi_read(buff, addr, count * MSC_BLOCK_SIZE) != HAL_OK) {
        return RES_ERROR;
    }
    return RES_OK;
}

DRESULT disk_write(BYTE pdrv, const BYTE *buff, LBA_t sector, UINT count) {
    if (pdrv != 0) return RES_PARERR;
    if (sector + count > MSC_BLOCK_COUNT) return RES_PARERR;

    // CMD_WRITE_PAGE arbeitet dagegen page-weise, darum je Sektor ein Aufruf.
    for (UINT i = 0; i < count; i++) {
        uint32_t addr = MSC_RESERVED + ((uint32_t)sector + i) * MSC_BLOCK_SIZE;
        if (qspi_write((uint8_t *)(buff + (size_t)i * MSC_BLOCK_SIZE), addr, MSC_BLOCK_SIZE) != HAL_OK) {
            return RES_ERROR;
        }
    }
    return RES_OK;
}

DRESULT disk_ioctl(BYTE pdrv, BYTE cmd, void *buff) {
    if (pdrv != 0) return RES_PARERR;

    switch (cmd) {
    case CTRL_SYNC:
        // qspi_write() pollt bis WIP geloescht ist, es steht nichts aus.
        return RES_OK;

    case GET_SECTOR_COUNT:
        *(LBA_t *)buff = MSC_BLOCK_COUNT;
        return RES_OK;

    case GET_SECTOR_SIZE:
        *(WORD *)buff = MSC_BLOCK_SIZE;
        return RES_OK;

    case GET_BLOCK_SIZE:
        // In Sektoren, nicht in Bytes: die Erase Sektorgroesse des M95P16.
        *(DWORD *)buff = M95P16_FLASH_SECTOR_SIZE / MSC_BLOCK_SIZE;
        return RES_OK;

    default:
        return RES_PARERR;
    }
}

/*
 * Von ff.c erwartet, solange FF_FS_NORTC = 0 ist. Das Board hat keinen RTC,
 * also eine feste Zeitmarke - sonst gaebe es einen Linker Fehler.
 * Format: bit31..25 Jahr ab 1980, bit24..21 Monat, bit20..16 Tag,
 *         bit15..11 Stunde, bit10..5 Minute, bit4..0 Sekunde/2.
 */
DWORD get_fattime(void) {
    return ((DWORD)(2026 - 1980) << 25) | ((DWORD)1 << 21) | ((DWORD)1 << 16);
}
