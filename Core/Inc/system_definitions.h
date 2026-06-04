/*
 * system_definition.h
 *
 *  Created on: 26.05.2026
 *      Author: tba
 */

#ifndef INC_SYSTEM_DEFINITIONS_H_
#define INC_SYSTEM_DEFINITIONS_H_
#ifndef MY_BUTTON_CNT
#define MY_BUTTON_CNT 8
#endif

#ifndef TX_BUFFER_SIZE
#define TX_BUFFER_SIZE 96
#endif
#ifndef RX_BUFFER_SIZE
#define RX_BUFFER_SIZE TX_BUFFER_SIZE
#endif

#define USB_TX_BUFFER_SIZE 1024
#define SYNCHRONIZATION_THRESHOLD 15 // How many correct slot are received
#define CYCLE_MS           1      // Time in ms for loop
#define PRE_SUBSLOT_CNT    4     // How much subslot in the earlier frame is it allowed to send
#define RADIO_CNT_MAX      120
#define BLINKING_CNT       500  // Key led blinking update multiplied by slot time
#define BLINKING_IT_CNT    5
#define BUF_SIZ 16
#define MAX_HUB_CNT 1
#define KEEP_ALIVE_CYCLE_CNT (uint16_t)30 // is set so that at least once in a KEEP_ALIVE_CYCLE_CNT Frame cycle a frame is sent
#define MY_SLOT_CNT 8
#define MAX_SEND_SUB_SLOT_CNT 1
#define SUB_SLOT_POW2 3
#define SUB_SLOT_CNT (1<<SUB_SLOT_POW2)
#define SUB_SLOT_MASK (SUB_SLOT_CNT-1)
#define SLOT_POW2 4
#define SLOT_CNT (1<<SLOT_POW2)
#define SLOT_MASK (SLOT_CNT-1)
#define SLOT_SHIFT (SUB_SLOT_POW2)

#define KEEP_ALIVE_CYCLE_VALUE  (int16_t)KEEP_ALIVE_CYCLE_CNT*SLOT_CNT
#define TIME_SUB_SLOT_DURATIOM_MS 2.5
#define USE_26MHz_OSCI 1 // Osci not crystal!
#define ACTIVE_SLOT_USAGE 0.5

typedef enum {
  user_led,     // 0
  radio_led,    // 1
  debug_pin,    // 2
  sSlot_pin,    // 3
  slot_pin,     // 4
  cycle_pin,    // 5
  send_pin,     // 6
  RB_USER_LED_LED_CNT
} user_pin_e;

#endif /* INC_SYSTEM_DEFINITIONS_H_ */
