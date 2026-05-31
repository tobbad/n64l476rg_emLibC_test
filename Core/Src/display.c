/*
 * diaplay.c
 *
 *  Created on: Oct 28, 2024
 *      Author: TBA
 */
#include "display.h"
#include "common.h"
#include "main.h"
#include "ssd1306_fonts.h"
#include "state.h"

const allign_e def_alli              = Centered;
char          *state_to_str[LOC_CNT] = {
    (char *)&"OF",
    (char *)&"BL",
    (char *)&"ON",
};

char line[MAX_BUTTON_CNT * 2 + 1];

typedef struct line_s {
    allign_e    align;
    char        line[CHAR_PER_LINE];
    key_state_e attr;
    bool        dirty;
    uint16_t    crc;

} line_t;

typedef struct display_s {
    uint8_t               cycle_size;
    state_t              *state;
    state_t               lstate;
    line_t                line[LINE_CNT];
    const SSD1306_Font_t *font;
    uint8_t               char_x;
    uint8_t               char_y;
    bool                  init;
    bool                  dirty;
} display_t;

static display_t my_display;
static void      display_states_update(bool doShowLine);
static void      display_lines(bool doShowLine);
static bool      display_is_dirty();
static void      display_states_update(bool doShowLine);

void display_init(state_t *state, uint16_t cycle_size, const SSD1306_Font_t *font) {
    char _line[CHAR_PER_LINE];
    my_display.state      = state;
    my_display.cycle_size = cycle_size;
    my_display.font       = font;
    my_display.char_x     = SSD1306_WIDTH / my_display.font->width;
    my_display.char_y     = SSD1306_HEIGHT / my_display.font->height;
    if (HAL_I2C_IsDeviceReady(&hi2c1, SSD1306_I2C_ADDR, 3, 100) == HAL_OK) {
        // Display erreichbar
        ssd1306_Init();
    } else {
        // Bus immer noch blockiert – Hardware prüfen
        my_display.init = false;
        printf("No display" NL);
        return;
    }
    ssd1306_SetDisplayOn(true);
    ssd1306_Fill(Black);
    ssd1306_SetCursor(0, 0);

    memset(_line, 0, CHAR_PER_LINE);
    for (uint8_t i = 0; i < state->cnt; i++) {
        _line[2 * i]     = my_display.state->label[i + state->first];
        _line[2 * i + 1] = ' ';
    }
    display_write_txt2line(LABEL, _line, Left);
    for (uint8_t lineNr = 0; lineNr < LINE_CNT; lineNr++) {
        if (lineNr == LABEL)
            continue;
        memset(my_display.line[lineNr].line, 0, CHAR_PER_LINE);
        my_display.line[lineNr].align = Left;
        my_display.line[lineNr].dirty = true;
        display_setAttr(lineNr, ON);
    }
    my_display.init   = true;
    my_display.lstate = *state;
    display_lines(true);
    ssd1306_UpdateScreen();
}

void display_update() {
    static uint8_t idx = 0;
    if (!my_display.init) return;
    if (!display_is_dirty())
        return;
    bool doShow = true; // idx < my_display.cycle_size << 1;
    display_states_update(doShow);
    display_lines(doShow);
    my_display.lstate = *my_display.state;
    ssd1306_UpdateScreen();
    idx++;
    my_display.dirty = false;
}

void display_clear_line(line_e lineNr) {
    if (!my_display.init) return;
    uint8_t y_start = lineNr * DOT_PER_LINE;
    uint8_t y_stop  = (lineNr + 1) * DOT_PER_LINE - 1;
    ssd1306_FillRectangle(0, y_start, SSD1306_WIDTH - 1, y_stop, Black);
    ssd1306_UpdateScreen();
}

void display_write_txt2line(line_e lineNr, const char *text, allign_e loc) {
    if (!my_display.init) return;
    uint8_t len = strlen(text);
    len         = MIN(CHAR_PER_LINE, len);
    memset(my_display.line[lineNr].line, 0, CHAR_PER_LINE);
    memcpy(my_display.line[lineNr].line, text, len);
    my_display.line[lineNr].attr  = ON;
    uint16_t crc                  = common_crc16((uint8_t *)&my_display.line[lineNr].line, len);
    my_display.line[lineNr].align = loc;
    my_display.line[lineNr].dirty = (crc != my_display.line[lineNr].crc);
    my_display.line[lineNr].crc   = crc;
    my_display.dirty |= my_display.line[lineNr].dirty;
}

void display_setAttr(line_e lineNr, key_state_e attr) {
    if (!my_display.init) return;
    my_display.line[lineNr].attr  = attr;
    my_display.line[lineNr].dirty = true;
    my_display.dirty              = true;
}

bool display_is_dirty() {
    if (!my_display.init) return false;
    my_display.dirty = false;
    for (uint8_t lineNr = 0; lineNr < LINE_CNT; lineNr++) {
        my_display.dirty |= my_display.line[lineNr].dirty;
    }
    return my_display.dirty = my_display.dirty || !state_is_same(&my_display.lstate, my_display.state);
}
static void display_states_update(bool doShowLine) {
    if (!my_display.init) return;
    for (uint8_t i = 0; i < my_display.state->cnt; i++) {
        uint8_t idx = i + my_display.state->first;
        if (my_display.state->state[idx] == OFF) {
            memcpy(&my_display.line[STATE].line[2 * i], (uint8_t *)&"  ", 2);
        } else if (my_display.state->state[idx] == BLINKING) {
            if (doShowLine) {
                memcpy(&my_display.line[STATE].line[2 * i], state_to_str[my_display.state->state[idx]], 2);
            } else {
                memcpy(&my_display.line[STATE].line[2 * i], (void *)&"  ", 2);
            }
        } else {
            memcpy(&my_display.line[STATE].line[2 * i], state_to_str[my_display.state->state[idx]], 2);
        }
    }
    uint16_t crc                 = common_crc16((uint8_t *)&my_display.line[STATE].line, CHAR_PER_LINE - 1);
    my_display.line[STATE].dirty = (crc != my_display.line[STATE].crc);
    my_display.line[STATE].crc   = crc;
    my_display.dirty |= my_display.line[STATE].dirty;
}

static void display_lines(bool doShowLine) {
    if (!my_display.init) return;
    for (uint8_t lineNr = 0; lineNr < LINE_CNT; lineNr++) {
        if (!my_display.line[lineNr].dirty)
            continue;
        uint8_t strLen  = strlen(my_display.line[lineNr].line);
        uint8_t y_start = lineNr * DOT_PER_LINE + (my_display.font->height >> 1);
        uint8_t x_start = 0;
        if (my_display.line[lineNr].align == Centered) {
            x_start = (SSD1306_WIDTH - strLen * my_display.font->width) >> 1;
        }
        if (my_display.line[lineNr].align == Right) {
            x_start = SSD1306_WIDTH - 1 - (strLen * my_display.font->width);
        };
        display_clear_line(lineNr);
        ssd1306_SetCursor(x_start, y_start);
        if ((my_display.line[lineNr].attr == ON) || (my_display.line[lineNr].attr == BLINKING)) {
            ssd1306_WriteString(my_display.line[lineNr].line, *my_display.font, White);
        } else if ((my_display.line[lineNr].attr == BLINKING) && (doShowLine)) {
            ssd1306_WriteString(line, *my_display.font, White);
        }
        my_display.line[lineNr].dirty = false;
        ssd1306_UpdateScreen();
    }
    my_display.dirty = false;
}
