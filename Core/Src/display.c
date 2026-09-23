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

#define FULL_UPDATE 1

const allign_e def_alli = Centered;


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
    char                  lbl[CHAR_PER_LINE]; // shadow labels
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

void display_scan(){
    for (uint8_t adr=0;adr<0x80;adr++){
        if (HAL_I2C_IsDeviceReady(&hi2c1, adr, 3, 100) == HAL_OK) {
            // Display erreichbar
            printf("I2C Device on 0x%02x"NL, adr);
        }
    }
}
bool  display_init(state_t *state, uint16_t cycle_size, const SSD1306_Font_t *font) {
    my_display.state      = state;
    my_display.cycle_size = cycle_size;
    my_display.font       = font;
    my_display.char_x     = SSD1306_WIDTH / my_display.font->width;
    my_display.char_y     = SSD1306_HEIGHT / my_display.font->height;
    if (HAL_I2C_IsDeviceReady(&hi2c1, SSD1306_I2C_ADDR, 3, 100) == HAL_OK) {
        printf("Display detected on addr %02x"NL, SSD1306_I2C_ADDR);
        ssd1306_Init();
    } else{
        // Bus immer noch blockiert – Hardware prüfen
        my_display.init   = false;
        printf("No display"NL);
        return my_display.init;
    }
    if (my_display.font->height > DOT_PER_LINE){
        printf("Char height (%d) is larger then DOT_PER_LINE (%d)"NL,  my_display.font->height, DOT_PER_LINE);
    }
    ssd1306_SetCursor(0, 0);
    char _line[CHAR_PER_LINE];
    memset(_line, 0, CHAR_PER_LINE);
    for (uint8_t i = 0; i < my_display.state->cnt; i++) {
        _line[2 * i ] = ' ';
        _line[2 * i + 1] = my_display.state->label[i + my_display.state->first];
    }
    memcpy(my_display.lbl, _line, strlen(_line));
    my_display.init   = true;
    display_clear(true);
    my_display.lstate = *state;
    display_lines(true);
    ssd1306_UpdateScreen();
    return my_display.init;
}

void display_clear(bool header){
    if (!my_display.init)
        return;
    for (uint8_t lineNr = header?0:1; lineNr < LINE_CNT; lineNr++) {
        memset(my_display.line[lineNr].line, 0, CHAR_PER_LINE);
        my_display.line[lineNr].align = Left;
        my_display.line[lineNr].dirty = true;
        display_setAttr(lineNr, ON);
    }
}

void display_update(system_state_e state, bool force) {
    static uint8_t idx = 0;
    if (!my_display.init)
        return;
    if (!display_is_dirty())
        return;
    idx++;
    idx = idx%my_display.cycle_size;
    bool doShow = (idx<my_display.cycle_size)?true:false;
    if ((idx == 0)|| force){
        if ((state>=SYNCHRONIZE_READY) &&(state<SYNC_CNT)){
            my_display.lstate = *my_display.state;
            display_states_update(doShow);
            display_lines(doShow);
            ssd1306_UpdateScreen();
            my_display.dirty = false;
        }
    }
}

void display_clear_line(line_e lineNr) {
    if (!my_display.init) return;
    uint8_t y_start = lineNr * DOT_PER_LINE;
    uint8_t y_stop = (lineNr + 1) * DOT_PER_LINE - 1;
    ssd1306_FillRectangle(0, y_start, SSD1306_WIDTH - 1, y_stop, Black);
    ssd1306_UpdateScreen();
}
void display_set_label() {
    if (!my_display.init) return;
    memcpy(&my_display.line[LABEL], my_display.lbl, strlen(my_display.lbl));
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
    my_display.line[lineNr].attr  = attr;
    my_display.line[lineNr].dirty = true;
    my_display.dirty              = true;
}

bool display_is_dirty() {
    my_display.dirty = false;
    for (uint8_t lineNr = 0; lineNr < LINE_CNT; lineNr++) {
        my_display.dirty |= my_display.line[lineNr].dirty;
    }
    return my_display.dirty = my_display.dirty || !state_is_same(&my_display.lstate, my_display.state);
}
static void display_states_update(bool doShowLine) {
    for (uint8_t i = 0; i < my_display.state->cnt; i++) {
        uint8_t idx = i + my_display.state->first;
       char* sstr = state_key_string(OFF);
       if (my_display.state->state[idx] == OFF) {
            memcpy(&my_display.line[STATE].line[2 * i], (uint8_t *)(sstr), strlen(sstr));
        } else if (my_display.state->state[idx] == BLINKING) {
            if (doShowLine) {
                char* sstr = (uint8_t *)state_key_string(my_display.state->state[idx]);
                memcpy(&my_display.line[STATE].line[2 * i],sstr,  strlen(sstr));
            } else {
                memcpy(&my_display.line[STATE].line[2 * i], sstr, strlen(sstr));
            }
        } else {
            memcpy(&my_display.line[STATE].line[2 * i], sstr, strlen(sstr));
        }
    }
    uint16_t crc = common_crc16((uint8_t *)&my_display.line[STATE].line, CHAR_PER_LINE - 1);
    my_display.line[STATE].dirty = (crc != my_display.line[STATE].crc);
    my_display.line[STATE].crc = crc;
    my_display.dirty |= my_display.line[STATE].dirty;
}

static void display_lines(bool doShowLine) {
    if (!my_display.init)
        return;
    for (uint8_t lineNr = 0; lineNr < LINE_CNT - 1; lineNr++) {
        uint16_t crc = common_crc16((uint8_t *)&my_display.line[lineNr].line, CHAR_PER_LINE - 1);
        if ( crc == my_display.line[lineNr].crc ){
            continue;
        }
        uint8_t strLen  = strlen(my_display.line[lineNr].line);
        if (strLen==0) {
            display_clear_line(lineNr);
        }
        uint8_t y_start = lineNr * DOT_PER_LINE + ((my_display.font->height) >> 1);
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
            ssd1306_WriteString(my_display.line[lineNr].line, *my_display.font, White);
        }
        ssd1306_UpdateScreen();
        my_display.line[lineNr].dirty = false;
        my_display.line[lineNr].crc   = crc;
    }
    my_display.dirty = false;
}
