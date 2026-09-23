/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    quadspi.h
  * @brief   This file contains all the function prototypes for
  *          the quadspi.c file
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
/* USER CODE END Header */
/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __QUADSPI_H__
#define __QUADSPI_H__

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32l4xx_hal.h"
#include "m95p16.h"
#include "main.h"
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

extern QSPI_HandleTypeDef hqspi;

/* USER CODE BEGIN Private defines */
/* QSPI Error codes */
#define QSPI_OK            ((uint8_t)0x00)
#define QSPI_ERROR         ((uint8_t)0x01)
#define QSPI_BUSY          ((uint8_t)0x02)
#define QSPI_NOT_SUPPORTED ((uint8_t)0x04)
#define QSPI_SUSPENDED     ((uint8_t)0x08)
#define QSPI_SUSPENDED     ((uint8_t)0x08)
#define QSPI_SUSPENDED     ((uint8_t)0x08)
/* QSPI Info */
typedef struct
{
  uint32_t FlashSize;          /*!< Size of the flash */
  uint32_t EraseSectorSize;    /*!< Size of sectors for the erase operation */
  uint32_t EraseSectorsNumber; /*!< Number of sectors for the erase operation */
  uint32_t ProgPageSize;       /*!< Size of pages for the program operation */
  uint32_t ProgPagesNumber;    /*!< Number of pages for the program operation */
} QSPI_Info;

/* USER CODE END Private defines */

/* USER CODE BEGIN Prototypes */
HAL_StatusTypeDef qspi_read(uint8_t *pData, uint32_t ReadAddr, uint32_t Size);
HAL_StatusTypeDef qspi_write(uint8_t *pData, uint32_t WriteAddr, uint32_t Size);

/* Asynchroner Pfad: Datenphase per DMA, beim Schreiben danach Auto Polling per
   Interrupt auf das WIP Bit. Der Callback laeuft im QUADSPI bzw. DMA IRQ.
   Die HAL erlaubt nur eine QSPI Operation gleichzeitig; qspi_is_busy() fragt
   das ab. Die synchronen Varianten oben werden nur beim Boot von persistent.c
   benutzt, also bevor der erste asynchrone Transfer starten kann. */
typedef void (*qspi_done_cb_t)(bool ok);
bool              qspi_is_busy(void);
HAL_StatusTypeDef qspi_read_async(uint8_t *pData, uint32_t ReadAddr, uint32_t Size, qspi_done_cb_t cb);
HAL_StatusTypeDef qspi_write_async(uint8_t *pData, uint32_t WriteAddr, uint32_t Size, qspi_done_cb_t cb);
HAL_StatusTypeDef qspi_erase_page(uint32_t page_nr);
HAL_StatusTypeDef qspi_erase_sector(uint32_t Sector);
HAL_StatusTypeDef qspi_ease_chip(void);
uint8_t qspi_get_status(void);
uint8_t qspi_get_info(QSPI_Info *pInfo);


/* USER CODE END Prototypes */

#ifdef __cplusplus
}
#endif

#endif /* __QUADSPI_H__ */

