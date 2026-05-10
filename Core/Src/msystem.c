/*
 * msystem.c
 *
 *  Created on: 01.01.2026
 *      Author: badi
 */
#include "msystem.h"
#include "main.h"
#include "serial.h"
#include "stateled.h"
#include "stm32l4xx_it.h"
#ifndef USE_TINY_USB
#ifdef HAL_PCD_MODULE_ENABLED
#include "usbd_cdc_if.h"
#endif
#else
#ifdef USE_TINY_USB
#include "tusb.h"
#endif
#endif
#define COMMAND_LEN 15
// clang-format off
gpio_port_t user_pin = {
    .cnt = 3,
    .pin = {
        {.port = GPIOA, .pin = GPIO_PIN_9, .def = false, .inv = true,  .conf = {.Mode = GPIO_MODE_OUTPUT_PP, .Speed = GPIO_SPEED_FREQ_LOW, .Pull = GPIO_NOPULL}}, //  user_led_,
        {.port = GPIOC, .pin = GPIO_PIN_7, .def = false, .inv = true,  .conf = {.Mode = GPIO_MODE_OUTPUT_PP, .Speed = GPIO_SPEED_FREQ_LOW, .Pull = GPIO_NOPULL}}, //  radio_led_,
        {.port = GPIOD, .pin = GPIO_PIN_2, .def = false, .inv = false, .conf = {.Mode = GPIO_MODE_OUTPUT_PP, .Speed = GPIO_SPEED_FREQ_LOW, .Pull = GPIO_NOPULL}}, //  debug_pin_,
    }
};
// clang-format on

msystem_t msystem = {};

void helpAction(char *para);

void timingAction(char *para) {
    time_print(stxhdl, "Serial Timing", false, false);
    time_print(timehdl, "Timing", false, true);
}

void irqAction(char *para) {
    print_e save;
    save = serial_mode_get();
    serial_mode_set(RAW);
    // printf("# subslot   time"NL);
    // printf("irqTimimg = ["NL);
    for (uint8_t idx = 0; idx < SYSTEM_SLOT_CNT; idx++) {
        printf("      %3d  %9" PRId64 "  " NL, idx, irqtime[idx]);
    };
    // printf("]"NL);
    serial_mode_set(save);
}
void resetAction(char *para) {
    msystem_reset();
}

void stateAction(char *para) {
    printf("slot    = %d" NL, msystem.slot);
    printf("subSlot = %d" NL, msystem.subSlot);
    printf("sSlot   = %d" NL, msystem.sSlot);
    printf("actSlot = %d" NL, msystem.actSlot);
}

typedef struct cmd2action_s {
    char *cmd;
    void (*action)(char *);
    char *doc;
} cmd2action_t;

typedef struct cmd2aaction_s {
    uint8_t       cnt;
    uint8_t       max_len;
    cmd2action_t *action;
} cmd2aaction_t;

cmd2action_t actionsOnInput[] = {
    { .cmd = (char *)&"h", .action = &helpAction, .doc = (char *)&"h     : Print all supported commands" },
    { .cmd = (char *)&"help", .action = &helpAction, .doc = (char *)&"help  : Print all supported commands" },
    { .cmd = (char *)&"r", .action = &resetAction, .doc = (char *)&"r     : Reset board" },
    { .cmd = (char *)&"reset", .action = &resetAction, .doc = (char *)&"reset : Reset board" },
    { .cmd = (char *)&"t", .action = &timingAction, .doc = (char *)&"t     : Timing for tx USB/UART" },
    { .cmd = (char *)&"timing", .action = &timingAction, .doc = (char *)&"timing: Timing for tx USB/UART" },
    { .cmd = (char *)&"i", .action = &irqAction, .doc = (char *)&"i     : Show all ns in a cycle" },
};

cmd2aaction_t cmda2action = {
    .cnt     = ELCNT(actionsOnInput),
    .max_len = 0,
    .action  = (cmd2action_t *)&actionsOnInput
};

int8_t msystem_find_command(char *command) {
    int8_t res = -1;
    for (res = 0; res < cmda2action.cnt; res++) {
        if (strcmp(command, actionsOnInput[res].cmd) == 0) {
            return res;
        }
    }
    return -1;
}

void helpAction(char *para) {
    uint8_t idx;
    for (idx = 0; idx < cmda2action.cnt; idx++) {
        printf("%s" NL, actionsOnInput[idx].doc);
    }
}

void msystem_init(state_t *system_state) {
    msystem.user_pin     = &user_pin;
    msystem.system_state = system_state;
    msystem.sync_state   = SYNC_RESET;
    msystem.actSlot      = 0;
    msystem.slot         = -1;
    msystem.subSlot      = 0;
    msystem.cycle        = 0;
    GpioPortInit(msystem.user_pin);
    cmda2action.max_len = 0;
    for (uint8_t i = 0; i < cmda2action.cnt; i++) {
        cmda2action.max_len = MAX(cmda2action.max_len, strlen(actionsOnInput[i].cmd));
    }
    stateled_init(msystem.system_state, NULL, BLINKING_CNT * MY_SLOT_CNT, BLINKING_IT_CNT);
    printf("Maximal command length is %d" NL, cmda2action.max_len);
}

em_msg msystem_set_slot(int8_t slot) {
    if (msystem_check_slot(slot) >= 0) {
        msystem.actSlot = slot;
        msystem.subSlot = slot * TIME_IRQ_PER_SLOT;
        msystem.sSlot   = 0;
        return EM_OK;
    } else {
        return EM_ERR;
        printf("Set invalid slot %d" NL, slot);
    }
}

int8_t msystem_check_slot(int8_t slot) {
    if ((slot > 0) && (slot <= MY_SLOT_CNT)) {
        return slot;
    }
    return -1;
}

em_msg msystem_action(char *command) {
    em_msg      res = EM_OK;
    static char cmd[COMMAND_LEN];
    static char para[COMMAND_LEN];
    uint8_t     para_idx = 0;
    uint8_t     cmd_len  = strlen(command);
    if (cmd_len == 0) return EM_OK;
    if (cmd_len > COMMAND_LEN - 1) return EM_ERR;
    while (para_idx < COMMAND_LEN - 1 && isalnum((int)command[para_idx]))
        para_idx++;
    uint8_t cmd_min = MIN(cmd_len, para_idx);
    memset(cmd, 0, COMMAND_LEN);
    memset(para, 0, COMMAND_LEN);
    memcpy(para, &command[para_idx + 1], COMMAND_LEN - para_idx - 1);
    memcpy(cmd, command, cmd_min);
    int8_t idx = msystem_find_command(cmd);
    if (idx >= 0) {
        actionsOnInput[idx].action(para);
        return res;
    } else {
        return EM_ERR;
    }

    return EM_OK;
}
em_msg msystem_user_led_on(user_pin_e nr) {
    em_msg res = EM_ERR;
    if ((nr < 0) || (nr >= msystem.user_pin->cnt)) return res;
    res = GpioPinWrite((gpio_pin_t *)&msystem.user_pin->pin[nr], 1);
    return res;
}

em_msg msystem_user_led_off(user_pin_e nr) {
    em_msg res = EM_ERR;
    if ((nr < 0) || (nr >= msystem.user_pin->cnt)) return res;
    res = GpioPinWrite((gpio_pin_t *)&msystem.user_pin->pin[nr], 0);
    return res;
}

em_msg msystem_user_led_toggle(user_pin_e nr) {
    em_msg res = EM_ERR;
    if ((nr < 0) || (nr >= msystem.user_pin->cnt)) return res;
    res = GpioPinToggle((gpio_pin_t *)&msystem.user_pin->pin[nr]);
    return res;
}

void msystem_reset() {
    printf("System reboot");
    HAL_Delay(10);
    NVIC_SystemReset();
}
