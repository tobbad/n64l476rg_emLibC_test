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
#include "cycle.h"
#include "main.h"
#include "stm32l4xx_hal.h"
#include "tusb.h"
void tinyUSB_app_task(void) {
}

void tud_cdc_rx_cb(uint8_t itf) {
    uint32_t count = tud_cdc_n_available(itf);
    if (count > 0) {
        tud_cdc_n_read(itf, urx_buffer.mem, RX_BUFFER_SIZE);
        buffer_set(&urx_buffer, urx_buffer.mem, count);
        time_start(urxhdl, count, urx_buffer.mem, &msystem.cycle);
    }
}

void tud_cdc_tx_complete_cb(uint8_t itf) {
    time_stop(utxhdl, NULL);
}
