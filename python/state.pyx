# python/state.pyx
# cython: language_level=3
cimport state_decl as C
cimport common_decl as CM
cimport payload_decl as PL
cimport appliframe_decl as AF

from libc.stdint cimport uint8_t, uint32_t
import enum

class EmMsg(enum.IntEnum):
    ERR  = -1
    OK   =  0
    TRUE =  1
    @classmethod
    def check(cls, val):
        if int(val) < 0:
            raise RuntimeError(f"emLibC returned EM_ERR ({int(val)})")
        return cls(int(val))

class KeyState(enum.IntEnum):
    OFF      = 0
    BLINKING = 1
    ON       = 2
    @classmethod
    def _missing_(cls, value):
        return cls.OFF

cdef class PyState:
    cdef C.state_t _s
    def __cinit__(self):
        C.state_init(&self._s)
    @staticmethod
    def from_u32(uint32_t u32) -> "PyState":
        obj = PyState()
        C.state_set_u32(&(<PyState>obj)._s, u32)
        return obj
    @property
    def first(self): return self._s.first
    @first.setter
    def first(self, value): C.state_set_first(&self._s, <uint8_t>value)
    @property
    def cnt(self): return self._s.cnt
    @cnt.setter
    def cnt(self, value): C.state_set_cnt(&self._s, <uint8_t>value)
    @property
    def dirty(self): return bool(C.state_get_dirty(&self._s))
    @property
    def id(self): return self._s.id
    @property
    def clabel_cmd(self): return self._s.clabel.cmd
    @clabel_cmd.setter
    def clabel_cmd(self, value): self._s.clabel.cmd = value
    @property
    def labels(self): return self._s.label[:16].decode("latin-1")
    def get_key_by_lbl(self, str ch):
        cdef char c = <char>ord(ch[0])
        return KeyState(<int>C.state_get_key_by_lbl(&self._s, c))
    def set_key_by_lbl(self, str ch, key_state):
        cdef char c = <char>ord(ch[0])
        cdef int ks = int(key_state)
        C.state_set_key_by_lbl(&self._s, c, <C.key_state_e>ks)
    def propagate_by_lbl(self, str ch):
        cdef char c = <char>ord(ch[0])
        C.state_propagate_by_lbl(&self._s, c)
    def ch2idx(self, str ch):
        cdef char c = <char>ord(ch[0])
        return int(C.state_ch2idx(&self._s, c))
    def get_key_by_idx(self, idx):
        return KeyState(<int>C.state_get_key_by_idx(&self._s, <uint8_t>idx))
    def set_key_by_idx(self, idx, key_state):
        cdef int ks = int(key_state)
        C.state_set_key_by_idx(&self._s, <uint8_t>idx, <C.key_state_e>ks)
    def propagate_by_idx(self, idx): C.state_propagate_by_idx(&self._s, <uint8_t>idx)
    def get_u32(self): return int(C.state_get_u32(&self._s))
    def set_u32(self, uint32_t u32): C.state_set_u32(&self._s, u32)
    def set_dirty(self): C.state_set_dirty(&self._s)
    def set_undirty(self): C.state_set_undirty(&self._s)
    def reset(self): C.state_reset(&self._s)
    def copy_from(self, PyState src): C.state_copy(&src._s, &self._s)
    def is_same(self, PyState other): return int(C.state_is_same(&self._s, &other._s)) >= 0
    def diff(self, PyState other):
        result = PyState.__new__(PyState)
        C.state_init(&(<PyState>result)._s)
        C.state_diff(&self._s, &other._s, &(<PyState>result)._s)
        return result
    def merge(self, PyState other): return int(C.state_merge(&other._s, &self._s)) > 0
    def add(self, PyState delta): return int(C.state_add(&self._s, &delta._s)) > 0
    def check(self): return int(C.state_check(&self._s)) == 0
    def print(self, title=""):
        cdef bytes bt
        if title:
            bt = title.encode("utf-8")
            C.state_print(&self._s, bt)
        else:
            C.state_print(&self._s, NULL)
    def __repr__(self):
        states = [KeyState(<int>C.state_get_key_by_idx(&self._s, i)).name
                  for i in range(self._s.first, self._s.first + self._s.cnt)]
        return f"PyState(first={self._s.first}, cnt={self._s.cnt}, dirty={self.dirty}, states={states})"
    def __eq__(self, other):
        if isinstance(other, PyState): return self.is_same(<PyState>other)
        return NotImplemented
    def __getitem__(self, key):
        if isinstance(key, str): return self.get_key_by_lbl(key)
        return self.get_key_by_idx(key)
    def __setitem__(self, key, value):
        if isinstance(key, str): self.set_key_by_lbl(key, value)
        else: self.set_key_by_idx(key, value)

cdef class PyPayload:
    cdef PL.payload_t _p
    def __cinit__(self): PL.payload_init(&self._p)
    @property
    def slot(self): return self._p.slot
    @slot.setter
    def slot(self, value): PL.payload_set_slot(&self._p, <uint8_t>value)
    @property
    def hub_cnt(self): return self._p.hubCnt
    @property
    def init(self): return bool(self._p.init)
    @property
    def dirty(self): return bool(self._p.state.dirty)
    @property
    def state(self):
        s = PyState.__new__(PyState)
        C.state_copy(&self._p.state, &(<PyState>s)._s)
        return s
    def reset(self): PL.payload_reset(&self._p)
    def set_key(self, idx, key_state):
        cdef int ks = int(key_state)
        PL.payload_set(&self._p, <uint8_t>idx, <C.key_state_e>ks)
    def propagate_key(self, idx): PL.payload_propagateKey(&self._p, <uint8_t>idx)
    def set_dirty(self): PL.payload_set_dirty(&self._p)
    def set_undirty(self): PL.payload_set_undirty(&self._p)
    def merge(self, PyPayload other): return bool(PL.payload_merge(&other._p, &self._p))
    def copy_from(self, PyPayload src): PL.payload_copy(&src._p, &self._p)
    def check(self): return int(PL.payload_check(&self._p)) == 0
    def to_bytes(self):
        cdef uint8_t buf[64]
        PL.payload_copyPl2B(&self._p, buf)
        return bytes(buf[:sizeof(PL.payload_t)])
    def from_bytes(self, data):
        cdef const uint8_t *buf = data
        PL.payload_copyB2Pl(buf, &self._p)
    def print(self, title=""):
        cdef bytes bt
        if title:
            bt = title.encode("utf-8")
            PL.payload_print(&self._p, bt)
        else:
            PL.payload_print(&self._p, NULL)
    def __repr__(self):
        return f"PyPayload(slot={self._p.slot}, hubCnt={self._p.hubCnt}, init={self.init}, dirty={self.dirty})"

cdef class PyAppliFrame:
    cdef AF.AppliFrame_t _f
    def __cinit__(self): AF.AppliFrame_Init(&self._f)
    @property
    def cmd(self): return self._f.Cmd
    @cmd.setter
    def cmd(self, value): self._f.Cmd = <uint8_t>value
    @property
    def cmd_tag(self): return self._f.Cmdtag
    @property
    def cmd_type(self): return self._f.CmdType
    @property
    def cmd_len(self): return self._f.CmdLen
    @property
    def data_len(self): return self._f.DataLen
    @property
    def payload(self):
        pl = PyPayload.__new__(PyPayload)
        PL.payload_copy(&self._f.payload, &(<PyPayload>pl)._p)
        return pl
    def reset(self): AF.AppliFrame_Reset(&self._f)
    def undirty(self): AF.AppliFrame_Undirty(&self._f)
    def copy_from(self, PyAppliFrame src): AF.AppliFrame_Copy(&src._f, &self._f)
    def state_size(self): return int(AF.AppliFrame_StateSize(&self._f))
    def to_bytes(self):
        cdef uint8_t buf[64]
        cdef uint32_t n = AF.AppliFrame_CopyF2B(&self._f, buf)
        return bytes(buf[:n])
    def from_bytes(self, data):
        cdef const uint8_t *buf = data
        return int(AF.AppliFrame_CopyB2F(buf, &self._f))
    def copy_payload_to(self, PyPayload pl): AF.AppliFrame_CopyF2Pl(&self._f, &pl._p)
    def copy_payload_from(self, PyPayload pl): AF.AppliFrame_CopyPl2F(&pl._p, &self._f)
    def print(self, pkt_len=0, rxtx="", print_payload=True):
        cdef bytes brxtx
        if rxtx:
            brxtx = rxtx.encode("utf-8")
            AF.AppliFrame_Print(&self._f, <uint8_t>pkt_len, brxtx, print_payload)
        else:
            AF.AppliFrame_Print(&self._f, <uint8_t>pkt_len, NULL, print_payload)
    def __repr__(self):
        return f"PyAppliFrame(cmd=0x{self._f.Cmd:02X}, cmdTag={self._f.Cmdtag}, dataLen={self._f.DataLen})"
