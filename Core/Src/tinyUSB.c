/*
 * The MIT License (MIT)
 *
 * Copyright (c) 2019 Ha Thach (tinyusb.org)
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 *
 */
#include "tusb.h"
#include "stm32l4xx_hal.h"
#include "main.h"
#include "cycle.h"
#include <stdarg.h>
#include <stdio.h>


// Called by TU_ASSERT instead of "BKPT #0" (CFG_TUSB_DEBUG_BREAKPOINT in
// tusb_config.h). Records that an assert fired and where it came from, without
// halting the core. To catch one live, put a normal breakpoint on this function;
// rb_tusb_assert_from holds the caller address -> "info symbol" in gdb, or look
// it up in the .map file.
volatile uint32_t  rb_tusb_assert_cnt  = 0;
volatile void     *rb_tusb_assert_from = NULL;

void rb_tusb_assert_hook(void){
    rb_tusb_assert_cnt++;
    rb_tusb_assert_from = __builtin_return_address(0);
}

// Output for TU_LOG (CFG_TUSB_DEBUG_PRINTF in tusb_config.h). Writes straight to
// USART2, bypassing serial.c/printf() so that nothing here depends on the USB
// stack. Blocking on purpose: TU_LOG is also reached from the USB IRQ, where a
// buffered path could reorder or drop the very message we need.
int rb_tusb_printf(const char *format, ...){
    static char line[128];
    va_list args;

    va_start(args, format);
    int len = vsnprintf(line, sizeof(line), format, args);
    va_end(args);

    if (len <= 0) {
        return len;
    }
    if (len > (int)sizeof(line) - 1) {
        len = (int)sizeof(line) - 1;  // vsnprintf returns the untruncated length
    }
    HAL_UART_Transmit(&huart2, (uint8_t *)line, (uint16_t)len, 100);
    return len;
}

void tinyUSB_app_task(void){

}

void tud_cdc_rx_cb(uint8_t itf) {
    uint32_t count = tud_cdc_n_available(itf);
    if (count > 0) {
        tud_cdc_n_read(itf, urx_buffer.mem, RX_BUFFER_SIZE);
        buffer_set(&urx_buffer, urx_buffer.mem, count);
        time_start(urxhdl, count, urx_buffer.mem, &cycle);
    }
}

void tud_cdc_tx_complete_cb(uint8_t itf) {
    time_stop(utxhdl, NULL);
}
