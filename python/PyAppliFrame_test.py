import sys
sys.path.insert(0, "python/")
from PyAppliFrame import PyState, PyPayload, PyAppliFrame, EmMsg, KeyState
import PyAppliFrame as _mod

# Payload test
p = PyPayload()
p.set_key(0, KeyState.ON)
p.state.propagate_by_idx(1)        
p.print("test payload")

# AppliFrame test
f = PyAppliFrame()
f.print(pkt_len=52, rxtx="TX")

# Konstante
print(f"APPLIFRAME_SIZE_ON_AIR = {_mod.APPLIFRAME_SIZE_ON_AIR}")  # war: PyAppliframe (falscher Name)
