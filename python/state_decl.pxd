# python/state_decl.pxd
# Extern declarations for lib/emLibC/common/inc/state.h
#
# state_t memory layout (sizeof=40, key_state_e packed=1 byte):
#   first   @ 0   uint8
#   cnt     @ 1   uint8
#   dirty   @ 2   uint8
#   id      @ 3   uint8
#   clabel  @ 4   clabel_u (4 bytes)
#   state[] @ 8   uint8[16]  (key_state_e packed)
#   label[] @ 24  char[16]

from libc.stdint cimport uint8_t, uint32_t, int8_t
from common_decl cimport em_msg, clabel_u

cdef extern from "../lib/emLibC/common/inc/state.h":

    ctypedef enum key_state_e:
        OFF       = 0
        BLINKING  = 1
        ON        = 2
        STATE_CNT = 3

    int MAX_STATE_CNT   # 16

    ctypedef struct state_t:
        uint8_t  first
        uint8_t  cnt
        uint8_t  dirty
        uint8_t  id
        clabel_u clabel
        uint8_t  state[16]   # key_state_e __attribute__((packed)) = 1 byte
        char     label[16]

    ctypedef struct statea_t:
        uint8_t  range
        bint     dirty
        uint32_t state
        clabel_u clabel

    int8_t      state_ch2idx            (const state_t *s, char ch)
    int8_t      state_nr2idx            (state_t *s, uint8_t nr)
    em_msg      state_init              (state_t *s)
    em_msg      state_reset             (state_t *s)
    em_msg      state_set               (state_t *s, uint8_t nr, key_state_e ns)
    em_msg      state_set_state         (const state_t *src, state_t *dst)
    em_msg      state_check             (const state_t *s)
    em_msg      state_undirty           (state_t *s)
    key_state_e state_key_diff          (key_state_e s1, key_state_e s2)
    key_state_e state_get_key_by_lbl    (state_t *s, char ch)
    key_state_e state_get_key_by_idx    (state_t *s, uint8_t idx)
    em_msg      state_set_key_by_idx    (state_t *s, uint8_t nr, key_state_e ns)
    em_msg      state_set_key_by_lbl    (state_t *s, char ch, key_state_e ns)
    em_msg      state_propagate_by_lbl  (state_t *s, char ch)
    em_msg      state_propagate_by_idx  (state_t *s, uint8_t nr)
    em_msg      state_set_u32           (state_t *s, uint32_t u32)
    uint32_t    state_get_u32           (state_t *s)
    em_msg      state_copy              (const state_t *src, state_t *dst)
    em_msg      state_is_same           (state_t *last, state_t *cur)
    em_msg      state_diff              (state_t *ref, state_t *s, state_t *diff)
    em_msg      state_add               (state_t *inState, state_t *add)
    em_msg      state_merge             (state_t *inState, state_t *outState)
    em_msg      state_print             (const state_t *s, const char *title)
    em_msg      state_get_dirty         (state_t *s)
    em_msg      state_set_dirty         (state_t *s)
    em_msg      state_set_undirty       (state_t *s)
    uint8_t     state_get_cnt           (state_t *s)
    uint8_t     state_get_first         (state_t *s)
    em_msg      state_set_cnt           (state_t *s, uint8_t nr)
    em_msg      state_set_first         (state_t *s, uint8_t nr)
