/*
 * rb_system.h
 *
 *  Created on: 01.01.2026
 *      Author: badi
 */

#ifndef INC_SYSTEM_H_
#define INC_SYSTEM_H_
#include "common.h"
#include "cycle.h"
#include "gpio_port.h"
#include "buffer.h"
#include "device.h"
#include "system_definitions.h"
#ifndef MY_BUTTON_CNT
#define MY_BUTTON_CNT 8
#endif

typedef struct msystem_s{
    uint8_t      slot;
    int8_t       press;
    gpio_port_t  *user_pin;
    system_state_e sync_state;
    state_t *    system_state;
} msystem_t;

extern msystem_t msystem;
void msystem_init(state_t * system_state);
void msystem_reset();
void msystem_synchronize();
em_msg msystem_set_slot(int8_t slot, set_slot_e ss_type);
int8_t msystem_check_slot(int8_t slot);
system_state_e msystem_check_sync();
em_msg msystem_action(char *cmd);
em_msg msystem_user_led_on(user_pin_e nr);
em_msg msystem_user_led_off(user_pin_e nr);
em_msg msystem_user_led_toggle(user_pin_e nr);


#endif /* INC_SYSTEM_H_ */
