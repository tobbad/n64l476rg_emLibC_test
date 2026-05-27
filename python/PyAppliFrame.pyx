# python/PyAppliFrame.pyx
# cython: language_level=3
#
# Python bindings for emLibC: state_t, payload_t, AppliFrame_t
# Build: make   (from python/) or make python-build (from root)

cimport state_decl as C
cimport common_decl as CM
cimport payload_decl as PL
cimport appliframe_decl as AF

# Modulkonstante: entspricht #define APPLIFRAME_SIZE_ON_AIR sizeof(AppliFrame_t)
APPLIFRAME_SIZE_ON_AIR = sizeof(AF.AppliFrame_t)

from libc.stdint cimport uint8_t, uint32_t
from libc.string cimport memcpy
import enum


# ---------------------------------------------------------------------------
# Python enums
# ---------------------------------------------------------------------------

class EmMsg(enum.IntEnum):
    ERR  = -1
    OK   =  0
    TRUE =  1

    @classmethod
    def check(cls, val):
        if int(val) < 0:
            raise RuntimeError(f"emLibC EM_ERR ({int(val)})")
        return cls(int(val))


class CmdType(enum.IntEnum):
    RESET      = 0x00
    APPLI_CMD  = 0x11
    NWK_CMD    = 0x22
    KEEP_ALIVE = 0x33
    LED_TOGGLE = 0xff
    ACK_OK     = 0x01

    @classmethod
    def _missing_(cls, value):
        return cls.RESET


class KeyState(enum.IntEnum):
    OFF      = 0
    BLINKING = 1
    ON       = 2

    @classmethod
    def _missing_(cls, value):
        return cls.OFF


# ---------------------------------------------------------------------------
# PyState
# ---------------------------------------------------------------------------

cdef class PyState:
    """Wrapper around C state_t (40 bytes).

    Getter/Setter:
        first, cnt, dirty, id, clabel_cmd, labels
    Key access:
        get/set by label char or numeric index
    Serialisation:
        get_u32() / set_u32() / to_bytes() / from_bytes()
    """

    cdef C.state_t _s

    def __cinit__(self):
        C.state_init(&self._s)

    # --- factory ---
    @staticmethod
    def from_u32(uint32_t u32):
        obj = PyState()
        C.state_set_u32(&(<PyState>obj)._s, u32)
        return obj

    @staticmethod
    def from_bytes(data: bytes):
        obj = PyState()
        cdef const uint8_t *buf = data
        memcpy(<void*>&(<PyState>obj)._s, <const void*>buf, sizeof(C.state_t))
        return obj

    # --- scalar getters/setters ---

    @property
    def first(self) -> int:
        return self._s.first
    @first.setter
    def first(self, value):
        C.state_set_first(&self._s, <uint8_t>value)

    @property
    def cnt(self) -> int:
        return self._s.cnt
    @cnt.setter
    def cnt(self, value):
        C.state_set_cnt(&self._s, <uint8_t>value)

    @dirty.setter
    def dirty(self, value):
        if value:
            C.state_set_dirty(&self._s)
        else:
            C.state_set_undirty(&self._s)

    @property
    def id(self) -> int:
        return self._s.id

    @property
    def clabel_cmd(self) -> int:
        return self._s.clabel.cmd
    @clabel_cmd.setter
    def clabel_cmd(self, value):
        self._s.clabel.cmd = <int>value

    @property
    def clabel_str(self) -> str:
        return self._s.clabel.str[:4].decode("latin-1")
    @clabel_str.setter
    def clabel_str(self, value: str):
        cdef bytes b = value.encode("latin-1")[:4]
        for i in range(len(b)):
            self._s.clabel.str[i] = b[i]

    @property
    def labels(self) -> str:
        """16-char label array."""
        return self._s.label[:16].decode("latin-1")

    # --- key access by label char ---

    def get_key_by_lbl(self, str ch) -> KeyState:
        cdef char c = <char>ord(ch[0])
        return KeyState(<int>C.state_get_key_by_lbl(&self._s, c))

    def set_key_by_lbl(self, str ch, key_state) -> None:
        cdef char c = <char>ord(ch[0])
        cdef int ks = int(key_state)
        C.state_set_key_by_lbl(&self._s, c, <C.key_state_e>ks)

    def propagate_by_lbl(self, str ch) -> None:
        """Cycle OFF->BLINKING->ON->OFF by label."""
        cdef char c = <char>ord(ch[0])
        C.state_propagate_by_lbl(&self._s, c)

    def ch2idx(self, str ch) -> int:
        cdef char c = <char>ord(ch[0])
        return int(C.state_ch2idx(&self._s, c))

    # --- key access by index ---

    def get_key_by_idx(self, idx) -> KeyState:
        return KeyState(<int>C.state_get_key_by_idx(&self._s, <uint8_t>idx))

    def set_key_by_idx(self, idx, key_state) -> None:
        cdef int ks = int(key_state)
        C.state_set_key_by_idx(&self._s, <uint8_t>idx, <C.key_state_e>ks)

    def propagate_by_idx(self, idx) -> None:
        C.state_propagate_by_idx(&self._s, <uint8_t>idx)

    # --- serialisation ---

    def get_u32(self) -> int:
        return int(C.state_get_u32(&self._s))

    def set_u32(self, uint32_t u32) -> None:
        C.state_set_u32(&self._s, u32)

    def to_bytes(self) -> bytes:
        return bytes((<uint8_t*>&self._s)[:sizeof(C.state_t)])

    # --- bulk ops ---

    def reset(self) -> None:
        C.state_reset(&self._s)

    def copy_from(self, PyState src) -> None:
        C.state_copy(&src._s, &self._s)

    def is_same(self, PyState other) -> bool:
        return int(C.state_is_same(&self._s, &other._s)) >= 0

    def diff(self, PyState other):
        result = PyState.__new__(PyState)
        C.state_init(&(<PyState>result)._s)
        C.state_diff(&self._s, &other._s, &(<PyState>result)._s)
        return result

    def merge(self, PyState other) -> bool:
        return int(C.state_merge(&other._s, &self._s)) > 0

    def add(self, PyState delta) -> bool:
        return int(C.state_add(&self._s, &delta._s)) > 0

    def check(self) -> bool:
        return int(C.state_check(&self._s)) == 0

    def set_dirty(self) -> None:
        C.state_set_dirty(&self._s)

    def set_undirty(self) -> None:
        C.state_set_undirty(&self._s)

    def print(self, title: str = "") -> None:
        cdef bytes bt
        if title:
            bt = title.encode("utf-8")
            C.state_print(&self._s, bt)
        else:
            C.state_print(&self._s, NULL)

    # --- dunder ---

    def __repr__(self) -> str:
        states = [KeyState(<int>C.state_get_key_by_idx(&self._s, i)).name
                  for i in range(self._s.first, self._s.first + self._s.cnt)]
        return (f"PyState(first={self._s.first}, cnt={self._s.cnt}, "
                f"dirty={self.dirty}, id=0x{self._s.id:02X}, states={states})")

    def __eq__(self, other) -> bool:
        if isinstance(other, PyState):
            return self.is_same(<PyState>other)
        return NotImplemented

    def __getitem__(self, key):
        """s['A'] or s[3]"""
        if isinstance(key, str):
            return self.get_key_by_lbl(key)
        return self.get_key_by_idx(key)

    def __setitem__(self, key, value):
        """s['A'] = KeyState.ON  or  s[3] = KeyState.BLINKING"""
        if isinstance(key, str):
            self.set_key_by_lbl(key, value)
        else:
            self.set_key_by_idx(key, value)


# ---------------------------------------------------------------------------
# PyPayload
# ---------------------------------------------------------------------------

cdef class PyPayload:
    """Wrapper around C payload_t (44 bytes).

    Getter/Setter:
        slot, hub_cnt, init, conf, dirty
    Key access:
        set_key(idx, KeyState) / propagate_key(idx)
    Serialisation:
        to_bytes() / from_bytes()
    """

    cdef PL.payload_t _p

    def __cinit__(self):
        PL.payload_init(&self._p)

    # --- getters/setters ---

    @property
    def slot(self) -> int:
        return self._p.slot
    @slot.setter
    def slot(self, value):
        PL.payload_set_slot(&self._p, <uint8_t>value)

    @property
    def hub_cnt(self) -> int:
        return self._p.hubCnt
    @hub_cnt.setter
    def hub_cnt(self, value):
        self._p.hubCnt = <uint8_t>value

    @property
    def init(self) -> bool:
        return bool(self._p.init)

    @property
    def conf(self) -> int:
        return self._p.conf
    @conf.setter
    def conf(self, value):
        self._p.conf = <uint8_t>value

    @property
    def dirty(self) -> bool:
        return bool(self._p.state.dirty)
    @dirty.setter
    def dirty(self, value):
        if value:
            PL.payload_set_dirty(&self._p)
        else:
            PL.payload_set_undirty(&self._p)

    @property
    def state(self) -> PyState:
        """Return a copy of the embedded state_t as PyState."""
        s = PyState.__new__(PyState)
        C.state_copy(&self._p.state, &(<PyState>s)._s)
        return s


    # --- key access ---

    def set_key(self, idx, key_state) -> None:
        cdef int ks = int(key_state)
        PL.payload_set(&self._p, <uint8_t>idx, <C.key_state_e>ks)

    def propagate_key(self, idx) -> None:
        PL.payload_propagateKey(&self._p, <uint8_t>idx)

    # --- dirty ---

    def set_dirty(self) -> None:
        PL.payload_set_dirty(&self._p)

    def set_undirty(self) -> None:
        PL.payload_set_undirty(&self._p)

    # --- bulk ops ---

    def reset(self) -> None:
        PL.payload_reset(&self._p)

    def merge(self, PyPayload other) -> bool:
        return bool(PL.payload_merge(&other._p, &self._p))

    def copy_from(self, PyPayload src) -> None:
        PL.payload_copy(&src._p, &self._p)

    def check(self) -> bool:
        return int(PL.payload_check(&self._p)) == 0

    # --- serialisation ---

    def to_bytes(self) -> bytes:
        cdef uint8_t buf[44]
        PL.payload_copyPl2B(&self._p, buf)
        return bytes(buf[:44])

    def from_bytes(self, data: bytes) -> None:
        cdef const uint8_t *buf = data
        PL.payload_copyB2Pl(buf, &self._p)

    def print(self, title: str = "") -> None:
        cdef bytes bt
        if title:
            bt = title.encode("utf-8")
            PL.payload_print(&self._p, bt)
        else:
            PL.payload_print(&self._p, NULL)

    def __repr__(self) -> str:
        return (f"PyPayload(slot={self._p.slot}, hubCnt={self._p.hubCnt}, "
                f"init={self.init}, conf=0x{self._p.conf:02X}, dirty={self.dirty})")


# ---------------------------------------------------------------------------
# PyAppliFrame
# ---------------------------------------------------------------------------

cdef class PyAppliFrame:
    """Wrapper around C AppliFrame_t (52 bytes).

    Getter/Setter:
        cmd, cmd_tag, cmd_type, cmd_len, data_len, conf
    Payload access:
        payload (returns PyPayload copy)
        copy_payload_to(pl) / copy_payload_from(pl)
    Serialisation:
        to_bytes() / from_bytes()
    """

    cdef AF.AppliFrame_t _f

    def __cinit__(self):
        AF.AppliFrame_Init(&self._f)

    # --- getters/setters ---

    @property
    def cmd(self) -> int:
        return self._f.Cmd
    @cmd.setter
    def cmd(self, value):
        self._f.Cmd = <uint8_t>value

    @property
    def cmd_tag(self) -> int:
        return self._f.Cmdtag
    @cmd_tag.setter
    def cmd_tag(self, value):
        self._f.Cmdtag = <uint8_t>value

    @property
    def cmd_type(self) -> uint8_t:
        return self._f.CmdType
    @cmd_type.setter
    def cmd_type(self, value):
        self._f.CmdType = <uint8_t>value

    @property
    def cmd_len(self) -> int:
        return self._f.CmdLen
    @cmd_len.setter
    def cmd_len(self, value):
        self._f.CmdLen = <uint8_t>value

    @property
    def data_len(self) -> int:
        return self._f.DataLen
    @data_len.setter
    def data_len(self, value):
        self._f.DataLen = <uint8_t>value

    @property
    def conf(self) -> bytes:
        """3-byte conf field as bytes."""
        return bytes(self._f.conf[:3])
    @conf.setter
    def conf(self, value: bytes):
        for i in range(min(3, len(value))):
            self._f.conf[i] = value[i]

    @property
    def payload(self) -> PyPayload:
        """Return a PyPayload copy of the embedded payload."""
        pl = PyPayload.__new__(PyPayload)
        PL.payload_copy(&self._f.payload, &(<PyPayload>pl)._p)
        return pl

    # --- payload helpers ---

    def copy_payload_to(self, PyPayload pl) -> None:
        AF.AppliFrame_CopyF2Pl(&self._f, &pl._p)

    def copy_payload_from(self, PyPayload pl) -> None:
        AF.AppliFrame_CopyPl2F(&pl._p, &self._f)

    # --- frame ops ---

    def reset(self) -> None:
        AF.AppliFrame_Reset(&self._f)

    def undirty(self) -> None:
        AF.AppliFrame_Undirty(&self._f)

    def copy_from(self, PyAppliFrame src) -> None:
        AF.AppliFrame_Copy(&src._f, &self._f)

    def state_size(self) -> int:
        return int(AF.AppliFrame_StateSize(&self._f))

    # --- serialisation ---

    def to_bytes(self) -> bytes:
        cdef uint8_t buf[52]
        cdef uint32_t n = AF.AppliFrame_CopyF2B(&self._f, buf)
        return bytes(buf[:n])

    def from_bytes(self, data: bytes) -> int:
        cdef const uint8_t *buf = data
        return int(AF.AppliFrame_CopyB2F(buf, &self._f))

    def print(self, pkt_len: int = 0, rxtx: str = "",
              print_payload: bool = True) -> None:
        cdef bytes brxtx
        if rxtx:
            brxtx = rxtx.encode("utf-8")
            AF.AppliFrame_Print(&self._f, <uint8_t>pkt_len, brxtx, print_payload)
        else:
            AF.AppliFrame_Print(&self._f, <uint8_t>pkt_len, NULL, print_payload)

    def __repr__(self) -> str:
        return (f"PyAppliFrame(cmd=0x{self._f.Cmd:02X}, "
                f"cmdTag={self._f.Cmdtag}, dataLen={self._f.DataLen})")
