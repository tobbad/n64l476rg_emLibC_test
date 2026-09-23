/*
 * msc_disc.h
 *
 *  Created on: 04.04.2026
 *      Author: badi
 */

#ifndef INC_MSC_DISC_H_
#define INC_MSC_DISC_H_

#include "qspi.h"

// Geometrie des Datentraegers im M95P16 (2 MB, 4096 Pages a 512 B).
// Page 0 haelt den Konfigurationssatz von persistent.c (START_READ_ADDR = 0,
// PERSISTENT_SIZE = 32). Damit ein Sector Erase die Konfiguration nicht
// mitnimmt, beginnt die Disk erst hinter dem ersten Erase Sektor.
// Wird von msc_disc.c (USB MSC) und diskio.c (FatFs) gemeinsam benutzt.
#define MSC_RESERVED    M95P16_FLASH_SECTOR_SIZE
#define MSC_BLOCK_SIZE  M95P16_FLASH_PAGE_SIZE
#define MSC_BLOCK_COUNT ((M95P16_FLASH_SIZE - MSC_RESERVED) / MSC_BLOCK_SIZE)

typedef enum {
    MSC_STATE_UNKNOWN = 0,
    MSC_STATE_MOUNTED,      // gueltiger Bootsektor gefunden
    MSC_STATE_FORMATTED,    // war leer, wurde mit FAT12 beschrieben
    MSC_STATE_READ_ERROR,
    MSC_STATE_FORMAT_ERROR,
} msc_state_e;

// Prueft den Datentraeger im M95P16 und formatiert ihn, falls kein gueltiger
// Bootsektor vorhanden ist. Muss vor tusb_init() aufgerufen werden.
void msc_disk_init(void);
msc_state_e msc_get_state(void);
void msc_print_info(void);

#endif /* INC_MSC_DISC_H_ */
