/*
 * display.h
 *
 *  Created on: Oct 28, 2024
 *      Author: TBA
 */

#ifndef INC_DISPLAY_H_
#define INC_DISPLAY_H_
#include "common.h"
#include "state.h"
#include "ssd1306_fonts.h"
#define DOT_PER_LINE 16
#define CHAR_PER_LINE (SSD1306_WIDTH/7 + 1)

typedef enum {
    Centered =0,
    Left,
    Right,
    LOC_CNT
} allign_e;
typedef enum {
    HEADING, LABEL, STATE, LINE_CNT
} line_e;

#define DOT_PER_LINE 16
#define DISPLAY_LINE_CNT SSD1306_HEIGHT/(10)-1
#define CHAR_PER_LINE    (SSD1306_WIDTH/7 + 1)

//extern char* state2str[];
#define ENTRY_SIZE 3
extern char *state_to_str[LOC_CNT];
void display_init(state_t *state, uint16_t cycle_size, const SSD1306_Font_t *font );
void display_update();
void display_setAttr(line_e lineNr, key_state_e attr);
void display_write_txt2line(line_e lineNr, const char * text, allign_e loc );
void display_write_line(line_e lineNr);
void display_clear_line(line_e lineNr);

#endif /* INC_DISPLAY_H_ */
