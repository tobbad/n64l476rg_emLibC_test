# python/common_decl.pxd
#
# Cython extern declarations for lib/emLibC/common/inc/common.h
# Compile with -DUNIT_TEST so hal_port.h / stm32l4xx.h are NOT pulled in.

from libc.stdint cimport uint8_t, uint16_t, uint32_t, int8_t, int32_t

cdef extern from "../lib/emLibC/common/inc/common.h":

    # ------------------------------------------------------------------
    # Constants
    # ------------------------------------------------------------------
    int MAX_BUTTON_CNT   # 16
    int CMD_LEN          # 4

    # ------------------------------------------------------------------
    # em_msg  (return code enum)
    # ------------------------------------------------------------------
    ctypedef enum em_msg:
        EM_ERR  = -1
        EM_OK   =  0
        EM_TRUE =  1
        
    ctypedef enum type_e:
        hexnum  = 0x10,
        ascii   = 0x20,
        nonasci = 0x80

        # ------------------------------------------------------------------
    # clabel_u  (union: int32 cmd  OR  char[4] str)
    # ------------------------------------------------------------------
    ctypedef union clabel_u:
        int32_t cmd
        char    str[4]   # CMD_LEN

    ctypedef struct idx2str_t:
        char    str[26]
        uint8_t idx

    ctypedef struct idxa2str_t:
        uint8_t    cnt
        idx2str_t *entry
        
    
    
    # ------------------------------------------------------------------
    # Utility functions exposed from common.c
    # ------------------------------------------------------------------
    uint16_t common_crc16(const uint8_t *data_p, uint16_t length)
    char*    idxa2str    (idxa2str_t *map, uint8_t idx)
    char*    idx2str     (idx2str_t  *map, uint8_t cnt, uint8_t idx)
    char     int2hchar   (uint8_t idx)
    type_e   clable2type (clabel_u *lbl)
    int8_t   clabel2uint8(clabel_u *lbl)
