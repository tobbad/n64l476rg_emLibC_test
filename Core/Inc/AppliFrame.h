/*
 * AppliFame.h
 *
 *  Created on: Sep 9, 2024
 *      Author: TBA
 */

#ifndef APP_APPLIFRAME_H_
#define APP_APPLIFRAME_H_
#include "common.h"
#include "payload.h"
#include "device.h"
#include <assert.h>

typedef enum {
    appliframe_slow = 1, // Higher slot time for data xchange
    appliframe_sync = 2, // Setze System in Synchronisation state
} conf_e;

typedef enum __attribute__((packed)) {
    CMDT_RESET      = 0x0,
    CMDT_APPLI_CMD  = 0x11,
} cmd_type_e;

typedef enum __attribute__((packed)) {
    CMD_RESET      = 0x0,
    CMD_KEEP_ALIVE = 0x33,
    CMD_LED_TOGGLE = 0xff,
    CMD_ACK_OK     = 0x01,
    CMD_NWK_CMD    = 0x22,
} cmd_e;

typedef struct AppliFrame_s {
    uint8_t    Cmdtag;
    cmd_type_e CmdType;
    uint8_t    CmdLen;
    cmd_e      Cmd;
    uint8_t    DataLen; // 5 Bytes
    uint8_t    slot; // 6,
    uint8_t    conf[2]; // 7, 8
    payload_t  payload; // 44 Byte
} AppliFrame_t; // header size is payload (44 Byte) + 8 = 52 Byte
#define FRAME_HEADER_SIZE sizeof(AppliFrame_t)- sizeof(payload_t)
extern AppliFrame_t rxFrame;
extern AppliFrame_t txFrame;
extern payload_t *rxPayload;
extern payload_t *txPayload;
extern AppliFrame_t keepAlivePackage;
#define APPLIFRAME_SIZE_ON_AIR sizeof(AppliFrame_t)
#define APPLIFRAME_HEADER sizeof(AppliFrame_t) - sizeof(payload_t)

void AppliFrame_Init(AppliFrame_t *frame, int8_t slot);
void AppliFrame_Reset(AppliFrame_t *frame);
bool AppliFrame_IsDirty(AppliFrame_t *frame);
void AppliFrame_SetDirty(AppliFrame_t *frame);
int8_t AppliFrame_GetSlot(AppliFrame_t *frame);
void AppliFrame_SetSlot(AppliFrame_t *frame, int8_t slot);
bool AppliFrame_CheckSlot(AppliFrame_t *frame);
void AppliFrame_Undirty(AppliFrame_t *frame);
void AppliFrame_Copy(const AppliFrame_t *from, AppliFrame_t *to);
uint8_t AppliFrame_StateSize(const AppliFrame_t *frame);
uint32_t AppliFrame_CopyF2B(const AppliFrame_t *frame, uint8_t *buffer);
uint32_t AppliFrame_CopyB2F(const uint8_t *buffer,  AppliFrame_t *frame );
uint32_t AppliFrame_CopyF2Pl(const AppliFrame_t *frame,  payload_t *payload);
uint32_t AppliFrame_CopyPl2F(const payload_t *payload, AppliFrame_t *frame);
void AppliFrame_Print(const AppliFrame_t *frame, char *rxtx, bool printPayload, bool doLong);

#endif /* APP_APPLIFRAME_H_ */
