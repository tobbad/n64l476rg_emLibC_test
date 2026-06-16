/*
 * radio.c
 *
 *  Created on: Jun 10, 2024
 *      Author: TBA
 */
#include "payload.h"
#include "state.h"
#include "options.h"

uint8_t payload_size = sizeof(payload_t);

void payload_init(payload_t * payload, uint8_t slot){
    if (!payload) return;
    memset(payload, -1, sizeof(payload_t));
    payload->slot   = slot;
    payload->hubCnt = 0;
    payload->conf   = PL_NO_ADD_ON_INFO;
    state_init(&payload->state);
    payload->init = true;
}

void payload_reset(payload_t *payload) {
    if (!payload->init) return;
    state_reset(&payload->state);
}

void payload_set(payload_t *payload, uint8_t nr, key_state_e st) {
    if (!payload->init) return;
    state_set(&payload->state, nr, st);
}

void payload_set_slot(payload_t *payload, uint8_t slot) {
    if (!payload->init) return;
    payload->slot = slot;
}

int8_t payload_get_slot(payload_t *payload) {
    if (!payload->init) return -1;
    return payload->slot;
}

void payload_set_dirty(payload_t *payload) {
    if (!payload->init)
        return;
    state_set_dirty(&payload->state);
}

bool payload_get_dirty(payload_t * payload){
    if (!payload->init)
         return false;
    return payload->state.dirty;
}

void payload_set_undirty(payload_t *payload) {
    if (!payload->init)  return;
    state_set_undirty(&payload->state);
}

em_msg payload_propagateKey(payload_t *payload, uint8_t nr) {
    if (!payload) return EM_ERR;
    return state_propagate_by_idx(&payload->state, nr);
}

void payload_copyB2Pl(const uint8_t *buffer, payload_t *payload) {
    if (!payload->init)  return;
    payload->slot        = *buffer++;
    payload->hubCnt      = *buffer++;
    payload->init        = *buffer++;
    payload->conf        = *buffer++;
    payload->state.first = *buffer++;
    payload->state.cnt   = *buffer++;
    payload->state.dirty = *buffer++;
    for (uint8_t i = 0; i < CMD_LEN; i++) {
        payload->state.clabel.str[i] = *buffer++;
    }
    for (uint8_t idx = 0; idx < MAX_BUTTON_CNT; idx++) {
        payload->state.state[idx] = *buffer++;
    }
    for (uint8_t idx = 0; idx < MAX_BUTTON_CNT; idx++) {
        payload->state.label[idx] = *buffer++;
    }
}

void payload_copyPl2B(const payload_t *payload, uint8_t *buffer) {
    if (!payload->init)
        return;
    *(buffer++) = payload->slot;
    *(buffer++) = payload->hubCnt;
    *(buffer++) = payload->init;
    *(buffer++) = payload->conf;
    *(buffer++) = payload->state.first;
    *(buffer++) = payload->state.cnt;
    *(buffer++) = payload->state.dirty;
    for (uint8_t i = 0; i < CMD_LEN; i++) {
        *buffer++ = payload->state.clabel.str[i];
    }
    for (uint8_t idx = 0; idx < MAX_BUTTON_CNT; idx++) {
        *(buffer++) = payload->state.state[idx];
    }
    for (uint8_t idx = 0; idx < MAX_BUTTON_CNT; idx++) {
        *(buffer++) = payload->state.label[idx];
    }
};

void payload_print(const payload_t *payload, const char *title, bool doLong) {
    if ((title != NULL) && (doLong)) {
        printf("%s" NL, title);
    }
    if (!payload->init) {
        print_buffer((uint8_t *)payload, sizeof(payload_t), "not initialized");
        return;
    }
    if (doLong) {
        printf("payload_t  = %u (size)" NL, sizeof(payload_t));
    }
    printf("PL slot    = %d" NL, payload->slot);
    printf("hubCnt     = %d" NL, payload->hubCnt);
    if (doLong) {
        printf("init       = %d" NL, payload->init);
        printf("conf       = %d" NL, payload->conf);
    }
    state_print(&payload->state, "state", doLong, &cycle);
}

em_msg payload_check(payload_t *pl) {
    if (pl == NULL) return false;
    return state_check(&pl->state);
};

bool payload_merge(payload_t *in, payload_t *out) {
    if (!in || !out) return false;
    state_merge(&in->state, &out->state);
    return true;
};

void payload_copy(const payload_t *in, payload_t *out) {
    if ((!in->init) && (out->init)) return;
    out->slot = in->slot;
    state_copy( &in->state, &out->state);
}
