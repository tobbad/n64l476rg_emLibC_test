/*
 * AppliFrame.c
 *
 *  Created on: Sep 11, 2024
 *      Author: TBA
 */

#define DUMMY 0xFF
#include "AppliFrame.h"
#include "main.h"
#include "common.h"
#include "msystem.h"
#include "payload.h"
#include "options.h"

#ifdef UNIT_TEST
    #define LED_TOGGLE    0xFF
    #define ACK_OK        0x01
#else
   // #include "p2p_demo_settings.h"
#endif

static idx2str_t cmd[] = {
    {.str = "RESET     ", .idx = CMD_RESET},      /*!< Inital state */
    {.str = "KEEP_ALIVE", .idx = CMD_KEEP_ALIVE},      /*!< Inital state */
    {.str = "LED_TOGGLE", .idx = CMD_LED_TOGGLE},  /*!< Toggle led */
    { .str ="CMD_ACK_OK", .idx = CMD_ACK_OK },   /*!< ACK of package */
    { .str ="NWK_CMD   ", .idx = CMD_NWK_CMD },   /*!< NACK of package */

};

idxa2str_t cmda2str={
    .cnt = ELCNT(cmd),
    .entry= (idx2str_t*)&cmd
};

static idx2str_t cmdtype2str[] = {
    { .str = "RESET     ", .idx = CMDT_RESET },     /*!< Inital state */
    { .str = "APPLI_CMD ", .idx = CMDT_APPLI_CMD }, /*!< Application frame */
};
idxa2str_t cmdt2str={
    .cnt = ELCNT(cmdtype2str),
    .entry= (idx2str_t*)&cmdtype2str
};

AppliFrame_t rxFrame;
payload_t *rxPayload = &rxFrame.payload;
state_t *rxState = &rxFrame.payload.state;

AppliFrame_t txFrame;
payload_t *txPayload = &txFrame.payload;
state_t *txState = &txFrame.payload.state;

AppliFrame_t keepAlivePackage;

void AppliFrame_Init(AppliFrame_t *frame, int8_t slot) {
    memset(frame, -1, sizeof(AppliFrame_t));
    frame->Cmd     = CMDT_RESET;
    frame->CmdLen  = 0;
    frame->Cmdtag  = 0;
    frame->CmdType = CMDT_RESET;
    frame->DataLen = sizeof(payload_t);
    AppliFrame_SetSlot(frame,  slot);
    memset(frame->conf, 0xff, 2);
    payload_init(&frame->payload, slot);
}

void AppliFrame_Reset(AppliFrame_t *frame) {
#if SYNCHRONIZE_DOING ==1
    printf("Reset payload AppliFrame @ addr %p" NL, frame);
#endif
    payload_reset(&frame->payload);
}
void AppliFrame_SetDirty(AppliFrame_t *frame) {
    payload_set_dirty(&frame->payload);
}

void AppliFrame_Undirty(AppliFrame_t *frame) {
    if (frame->payload.state.dirty){
        payload_set_undirty(&frame->payload);
    }
}

int8_t AppliFrame_GetSlot(AppliFrame_t *frame){
    return frame->slot;
}

void AppliFrame_SetSlot(AppliFrame_t *frame, int8_t slot){
    frame->slot = slot;
}

bool AppliFrame_CheckSlot(AppliFrame_t *frame){

    if (frame->slot != frame->payload.slot){
        return false;
    }
    if ((frame->slot<0) ||(frame->slot>=SYSTEM_SLOT_CNT)){
        return false;
    }
    return true;
}

bool AppliFrame_IsDirty(AppliFrame_t *frame) {
    if (frame->DataLen < sizeof(payload_t )) return false;
    return payload_get_dirty(&frame->payload);
}

uint8_t AppliFrame_StateSize(const AppliFrame_t *frame) {
    uint8_t toSend = sizeof(AppliFrame_t) - sizeof(payload_t) + frame->DataLen;
    return toSend;
}

void AppliFrame_Copy(const AppliFrame_t *from, AppliFrame_t *to) {
    memcpy(to, from, sizeof(AppliFrame_t));
}

uint32_t AppliFrame_CopyF2B(const AppliFrame_t *frame, uint8_t *buffer) {
    uint8_t cnt = AppliFrame_StateSize(frame);
    memcpy(buffer, (uint8_t *)frame, cnt);
    return cnt;
}

uint32_t AppliFrame_CopyB2F(const uint8_t *buffer, AppliFrame_t *frame) {
    uint8_t cnt = AppliFrame_StateSize((AppliFrame_t *)buffer);
    memcpy((uint8_t *)frame, buffer, cnt);
    frame->DataLen = sizeof(payload_t);
    return cnt;
}

uint32_t AppliFrame_CopyF2Pl(const AppliFrame_t *frame, payload_t *payload) {
    uint8_t  cnt  = sizeof(payload_t);
    uint8_t *from = (uint8_t *)&frame->payload;
    uint8_t *to   = (uint8_t *)payload;
    // printf("Copy %d bytes from from @%p to %p"NL, cnt, from, to);
    memcpy(to, from, cnt);
    return cnt;
}

uint32_t AppliFrame_CopyPl2F(const payload_t *payload, AppliFrame_t *frame) {
    memcpy((uint8_t *)&frame->payload, (uint8_t *)payload, sizeof(payload_t));
    return sizeof(payload_t);
}

void AppliFrame_Print(const AppliFrame_t *msg, char *rxtx, bool printPayload, bool doLong) {
    if (rxtx != NULL) {
        printf("%s: %s "NL, rxtx, cycle_string(&msystem.cycle));
    }
    int16_t pktLen = AppliFrame_StateSize(msg);
    if (doLong){
        printf("Packet len = %d "NL, pktLen);
        printf("Cmdtag     = %d" NL, msg->Cmdtag);
        printf("CmdType    = %s" NL, idxa2str(&cmdt2str, msg->CmdType));
        printf("CmdLen     = %d" NL, msg->CmdLen);
        printf("Cmd        = %s (%d)" NL, idxa2str(&cmda2str ,msg->Cmd), msg->Cmd);
        printf("DataLen    = %d" NL, msg->DataLen);
    }
    printf("AF slot    = %d" NL, msg->slot);
    if (doLong){
        printf("conf       = 0x%1x, 0x%1x " NL, msg->conf[0], msg->conf[1]);
        uint16_t crc = common_crc16((uint8_t *)msg, pktLen);
        printf("Crc        = 0x%04x" NL, crc);
    }
    if (printPayload) {
        if (msg->DataLen == 0){
            printf("No Payload"NL);
            return;
        }if (msg->DataLen == sizeof(payload_t)) {
            payload_print(&msg->payload, "PAYLOAD", doLong);
        } else {
            print_buffer((uint8_t*)&msg->payload, msg->DataLen, "Unknown payload");
        }
    }
}
