/*
 * radio.h
 *
 *  Created on: Jun 10, 2024
 *      Author: TBA
 */
#ifndef INC_PAYLOAD_H_
#define INC_PAYLOAD_H_
#include "common.h"
#include "state.h"

extern uint8_t payload_size;

typedef enum __attribute__((packed)){
    PL_NO_ADD_ON_INFO = 0xff,
} pl_conf_e;

#define PL_CONF_DEFAULT 0xff

typedef struct payload_s{
    uint8_t slot;
    uint8_t hubCnt;
    uint8_t init;
    pl_conf_e conf;
    state_t state; // is 40 Bytes
} payload_t; // size is 40 + 4 = 44

void payload_init(payload_t *payload, uint8_t slot);
void payload_reset(payload_t * payload);
void payload_set(payload_t * payload, uint8_t nr, key_state_e st);
void payload_set_slot(payload_t * payload, uint8_t slot);
int8_t payload_get_slot(payload_t * payload);
void payload_set_dirty(payload_t * payload);
bool payload_get_dirty(payload_t * payload);
void payload_set_undirty(payload_t * payload);
em_msg payload_propagateKey(payload_t * payload, uint8_t nr);
bool payload_merge(payload_t * in, payload_t * out);
void payload_copy(const payload_t * in, payload_t * out);
void payload_copyPl2B(const payload_t * payload, uint8_t *buffer);
void payload_copyB2Pl(const uint8_t *buffer, payload_t * payload);
bool payload_merge(payload_t * in, payload_t * out);
void payload_print(const payload_t * payload, const char *title, bool doLong);
em_msg payload_check(payload_t * pl);

#endif /* INC_PAYLOAD_H_ */
