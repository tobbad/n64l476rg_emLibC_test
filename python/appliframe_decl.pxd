# python/appliframe_decl.pxd
# Extern declarations for Core/Inc/AppliFrame.h
#
# AppliFrame_t memory layout (sizeof=52):
#   Cmdtag   @ 0   uint8
#   CmdType  @ 1   uint8
#   CmdLen   @ 2   uint8
#   Cmd      @ 3   uint8
#   DataLen  @ 4   uint8
#   conf[3]  @ 5   uint8[3]
#   payload  @ 8   payload_t (44 bytes)

from libc.stdint cimport uint8_t, uint32_t
from payload_decl cimport payload_t

cdef extern from "../Core/Inc/AppliFrame.h":


    ctypedef enum conf_e:
        appliframe_slow = 1
        appliframe_sync = 2

    ctypedef enum cmd_type_e:
        CMDT_RESET      = 0x00
        CMDT_APPLI_CMD  = 0x11
        CMDT_NWK_CMD    = 0x22
        CMDT_KEEP_ALIVE = 0x33
        CMDT_LED_TOGGLE = 0xff
        CMDT_ACK_OK     = 0x01

    ctypedef struct AppliFrame_t:
        uint8_t   Cmdtag
        uint8_t   CmdType
        uint8_t   CmdLen
        uint8_t   Cmd
        uint8_t   DataLen
        uint8_t   conf[3]
        payload_t payload

    void     AppliFrame_Init     (AppliFrame_t *f)
    void     AppliFrame_Reset    (AppliFrame_t *f)
    void     AppliFrame_Undirty  (AppliFrame_t *f)
    void     AppliFrame_Copy      (const AppliFrame_t *src, AppliFrame_t *dst)
    uint8_t  AppliFrame_StateSize(const AppliFrame_t *f)
    uint32_t AppliFrame_CopyF2B  (const AppliFrame_t *f, uint8_t *buf)
    uint32_t AppliFrame_CopyB2F  (const uint8_t *buf, AppliFrame_t *f)
    uint32_t AppliFrame_CopyF2Pl (const AppliFrame_t *f, payload_t *pl)
    uint32_t AppliFrame_CopyPl2F (const payload_t *pl, AppliFrame_t *f)
    void     AppliFrame_Print    (const AppliFrame_t *f, uint8_t pktLen,
                                   char *rxtx, bint printPayload)
