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
#ifndef MY_BUTTON_CNT
#define MY_BUTTON_CNT 8
#endif

#ifndef TX_BUFFER_SIZE
#define TX_BUFFER_SIZE 96
#endif
#ifndef RX_BUFFER_SIZE
#define RX_BUFFER_SIZE TX_BUFFER_SIZE
#endif

#define CYCLE_MS           30        // Time in ms for loop
#define RADIO_CNT_MAX      120
#define BLINKING_CNT       500  // Key led blinking update multiplied by slot time
#define BLINKING_IT_CNT    5
#define BUF_SIZ 16
#define MY_SLOT_CNT 8
#define SLOT_CNT 16
#define MAX_SEND_SUB_SLOT_CNT 2
#define TIME_IRQ_PER_SLOT 9
#define SYSTEM_IRQ_PER_CYCLE SYSTEM_SLOT_CNT*TIME_IRQ_PER_SLOT
#define TIME_SUB_SLOT_DURATIOM_MS 2.5
#define ACTIVE_SLOT_USAGE 0.5

typedef struct msystem_s{
    uint8_t      slot;
    cycle_t      cycle;
    gpio_port_t  *user_pin;
    system_state_e sync_state;
    state_t *    system_state;
} msystem_t;

typedef enum {
  user_led,
  radio_led,
  debug_pin,
  SYSTEM_USER_LED_LED_CNT
} user_pin_e;

extern msystem_t msystem;
void msystem_init(state_t * system_state);
void msystem_reset();
void msystem_synchronize();
em_msg msystem_set_slot(int8_t slot);
int8_t msystem_check_slot(int8_t slot);
system_state_e msystem_check_sync();
em_msg msystem_action(char *cmd);
em_msg msystem_user_led_on(user_pin_e nr);
em_msg msystem_user_led_off(user_pin_e nr);
em_msg msystem_user_led_toggle(user_pin_e nr);


#endif /* INC_SYSTEM_H_ */
