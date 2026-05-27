# python/payload_decl.pxd
# Extern declarations for Core/Inc/payload.h
#
# payload_t memory layout (sizeof=44, pl_conf_e packed=1 byte):
#   slot    @ 0   uint8
#   hubCnt  @ 1   uint8
#   init    @ 2   uint8
#   conf    @ 3   uint8 (pl_conf_e packed)
#   state   @ 4   state_t (40 bytes)

from libc.stdint cimport uint8_t
from common_decl cimport em_msg
from state_decl cimport state_t, key_state_e

cdef extern from "../Core/Inc/payload.h":

    ctypedef enum pl_conf_e:
        PL_NO_ADD_ON_INFO = 0xff

    ctypedef struct payload_t:
        uint8_t   slot
        uint8_t   hubCnt
        uint8_t   init
        uint8_t  conf     # pl_conf_e packed = 1 byte, no padding
        state_t  state    # 40 bytes @ offset 4

    void    payload_init        (payload_t *p)
    void    payload_reset       (payload_t *p)
    void    payload_set         (payload_t *p, uint8_t nr, key_state_e st)
    void    payload_set_slot    (payload_t *p, uint8_t slot)
    void    payload_set_dirty   (payload_t *p)
    void    payload_set_undirty (payload_t *p)
    em_msg  payload_propagateKey(payload_t *p, uint8_t nr)
    bint    payload_merge       (payload_t *inp, payload_t *out)
    void    payload_copyPl2B    (const payload_t *p, uint8_t *buf)
    void    payload_copyB2Pl    (const uint8_t *buf, payload_t *p)
    void    payload_print       (const payload_t *p, const char *title)
    em_msg  payload_check       (payload_t *p)
    void    payload_copy        (payload_t *inp, payload_t *out)
