/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    quadspi.c
  * @brief   This file provides code for the configuration
  *          of the QUADSPI instances.
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2025 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* Includes ------------------------------------------------------------------*/
#include "qspi.h"
#include "m95p16.h"

HAL_StatusTypeDef qspi_read(uint8_t *pData, uint32_t ReadAddr, uint32_t Size){
    HAL_StatusTypeDef status = QSPI_Read(&hqspi, pData, ReadAddr, Size);
    if (status!=HAL_OK) {
    	printf("Got error %02x reading qspi"NL, status);
    }
    return status;
}

HAL_StatusTypeDef qspi_write(uint8_t *pData, uint32_t WriteAddr, uint32_t Size){
    QSPI_WriteEnable(&hqspi);
    HAL_StatusTypeDef status = QSPI_Write(&hqspi, pData, WriteAddr, Size);
    return status;

}
HAL_StatusTypeDef qspi_erase_page(uint32_t page_nr){
    HAL_StatusTypeDef status = QSPI_PageErase(&hqspi, page_nr);
    return status;
}
HAL_StatusTypeDef qspi_erase_sector(uint32_t Sector){
    HAL_StatusTypeDef status = QSPI_SectorErase(&hqspi, Sector);
    return status;
}
HAL_StatusTypeDef qspi_erase_chip(void){
    HAL_StatusTypeDef status = QSPI_ChipErase(&hqspi);
    return status;

}
uint8_t qspi_get_status(void){
    uint8_t status;
    QSPI_ReadSatusReg(&hqspi, &status);
    return status;

}
uint8_t qspi_get_info(QSPI_Info *pInfo){
    /* Configure the structure with the memory configuration */
    pInfo->FlashSize          = M95P16_FLASH_SIZE;
    pInfo->EraseSectorSize    = M95P16_FLASH_SECTOR_SIZE;
    pInfo->EraseSectorsNumber = (pInfo->FlashSize / pInfo->EraseSectorSize );
    pInfo->ProgPageSize       = M95P16_FLASH_PAGE_SIZE;
    pInfo->ProgPagesNumber    = (pInfo->FlashSize / pInfo->ProgPageSize);
    return QSPI_OK;
}

/* ------------------------------------------------------------------------ */
/* Asynchroner Pfad                                                          */
/*                                                                           */
/* Die Datenphase laeuft per DMA (DMA1_Channel5, in MX_DMA_Init konfiguriert  */
/* und in HAL_QSPI_MspInit per __HAL_LINKDMA an hqspi gehaengt). Beim         */
/* Schreiben folgt danach das Warten auf das Ende des internen Page Write -   */
/* das ist mit ~5 ms der weitaus groessere Anteil und laeuft darum als        */
/* Auto Polling im Interrupt statt blockierend.                              */
/* ------------------------------------------------------------------------ */

typedef enum {
    QSPI_PHASE_IDLE = 0,
    QSPI_PHASE_READ,
    QSPI_PHASE_WRITE,   // Datenphase laeuft
    QSPI_PHASE_WAIT_WIP // Daten sind drin, Speicher schreibt intern
} qspi_phase_e;

static volatile qspi_phase_e qspi_phase = QSPI_PHASE_IDLE;
static qspi_done_cb_t        qspi_done  = NULL;

bool qspi_is_busy(void) {
    return qspi_phase != QSPI_PHASE_IDLE;
}

// Laeuft im IRQ. Erst aufraeumen, dann melden - der Callback darf sofort den
// naechsten Transfer starten.
static void qspi_finish(bool ok) {
    qspi_done_cb_t cb = qspi_done;
    qspi_done  = NULL;
    qspi_phase = QSPI_PHASE_IDLE;
    if (cb != NULL) {
        cb(ok);
    }
}

static void qspi_cmd_init(QSPI_CommandTypeDef *cmd, uint32_t instruction) {
    memset(cmd, 0, sizeof(*cmd));
    cmd->Instruction       = instruction;
    cmd->AddressSize       = QSPI_ADDRESS_24_BITS;
    cmd->DummyCycles       = 0;
    cmd->InstructionMode   = QSPI_INSTRUCTION_1_LINE;
    cmd->AddressMode       = QSPI_ADDRESS_1_LINE;
    cmd->AlternateByteMode = QSPI_ALTERNATE_BYTES_NONE;
    cmd->DataMode          = QSPI_DATA_1_LINE;
    cmd->DdrMode           = QSPI_DDR_MODE_DISABLE;
    cmd->DdrHoldHalfCycle  = QSPI_DDR_HHC_ANALOG_DELAY;
    cmd->SIOOMode          = QSPI_SIOO_INST_EVERY_CMD;
}

HAL_StatusTypeDef qspi_read_async(uint8_t *pData, uint32_t ReadAddr, uint32_t Size, qspi_done_cb_t cb) {
    if (qspi_is_busy()) {
        return HAL_BUSY;
    }
    QSPI_CommandTypeDef sCommand;
    qspi_cmd_init(&sCommand, CMD_READ_DATA);
    sCommand.Address = ReadAddr;
    sCommand.NbData  = Size;

    qspi_done  = cb;
    qspi_phase = QSPI_PHASE_READ;

    HAL_StatusTypeDef status = HAL_QSPI_Command(&hqspi, &sCommand, M95P16_QPSI_TIMEOUT_DEFAULT_VALUE);
    if (status == HAL_OK) {
        status = HAL_QSPI_Receive_DMA(&hqspi, pData);
    }
    if (status != HAL_OK) {
        qspi_done  = NULL;
        qspi_phase = QSPI_PHASE_IDLE;
    }
    return status;
}

HAL_StatusTypeDef qspi_write_async(uint8_t *pData, uint32_t WriteAddr, uint32_t Size, qspi_done_cb_t cb) {
    if (qspi_is_busy()) {
        return HAL_BUSY;
    }
    // Nur Kommandophase, kein Datentransfer - das blockiert nicht nennenswert.
    HAL_StatusTypeDef status = QSPI_WriteEnable(&hqspi);
    if (status != HAL_OK) {
        return status;
    }
    QSPI_CommandTypeDef sCommand;
    qspi_cmd_init(&sCommand, CMD_WRITE_PAGE);
    sCommand.Address = WriteAddr;
    sCommand.NbData  = Size;

    qspi_done  = cb;
    qspi_phase = QSPI_PHASE_WRITE;

    status = HAL_QSPI_Command(&hqspi, &sCommand, M95P16_QPSI_TIMEOUT_DEFAULT_VALUE);
    if (status == HAL_OK) {
        status = HAL_QSPI_Transmit_DMA(&hqspi, pData);
    }
    if (status != HAL_OK) {
        qspi_done  = NULL;
        qspi_phase = QSPI_PHASE_IDLE;
    }
    return status;
}

void HAL_QSPI_RxCpltCallback(QSPI_HandleTypeDef *local_hqspi) {
    (void)local_hqspi;
    if (qspi_phase == QSPI_PHASE_READ) {
        qspi_finish(true);
    }
}

void HAL_QSPI_TxCpltCallback(QSPI_HandleTypeDef *local_hqspi) {
    if (qspi_phase != QSPI_PHASE_WRITE) {
        return;
    }
    /* Die Daten sind im Speicher, jetzt laeuft dort der interne Schreibvorgang.
       Der HAL setzt State = READY bevor er hier landet, ein neuer Auftrag ist
       also erlaubt. Gewartet wird auf WIP == 0 (Bit 0 des Statusregisters). */
    QSPI_CommandTypeDef sCommand;
    qspi_cmd_init(&sCommand, CMD_READ_STATUS_REG);
    sCommand.AddressMode = QSPI_ADDRESS_NONE;
    sCommand.NbData      = 1;

    QSPI_AutoPollingTypeDef sConfig = {
        .Match           = 0x00,
        .Mask            = 0x01,
        .MatchMode       = QSPI_MATCH_MODE_AND,
        .StatusBytesSize = 1,
        .Interval        = 0x10,
        .AutomaticStop   = QSPI_AUTOMATIC_STOP_ENABLE,
    };

    qspi_phase = QSPI_PHASE_WAIT_WIP;
    if (HAL_QSPI_AutoPolling_IT(local_hqspi, &sCommand, &sConfig) != HAL_OK) {
        qspi_finish(false);
    }
}

void HAL_QSPI_StatusMatchCallback(QSPI_HandleTypeDef *local_hqspi) {
    (void)local_hqspi;
    if (qspi_phase == QSPI_PHASE_WAIT_WIP) {
        qspi_finish(true);
    }
}

void HAL_QSPI_ErrorCallback(QSPI_HandleTypeDef *local_hqspi) {
    (void)local_hqspi;
    if (qspi_is_busy()) {
        qspi_finish(false);
    }
}
/* USER CODE END 1 */
