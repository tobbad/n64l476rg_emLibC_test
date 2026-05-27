# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Test platform for the STM32L476RG microcontroller implementing a distributed button/keyboard state system with slot-based radio synchronization. Multiple devices each occupy a numbered slot (1, 3, 5, 7, 9, …, f) and exchange 52-byte `AppliFrame_t` packets. State changes propagate across all devices.

Three tightly coupled layers:
- **Firmware (C/STM32CubeIDE)** – the actual MCU application
- **emLibC** (`lib/emLibC/`, git submodule) – portable embedded C utilities used by the firmware and the Python bindings
- **Python/Cython** (`python/`) – Cython extension wrapping the C structs for simulation and log analysis

## Build commands

### Firmware (STM32CubeIDE)
Build from inside the IDE, or from the command line:
```bash
make -C Debug          # produces Debug/n64l476rg_emLibC_test.elf
```

### emLibC unit tests (GoogleTest + CMake)
```bash
cd lib/emLibC
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build
cd build && ctest -V
# or run a single test binary directly:
./build/state_test
```
Tests use AddressSanitizer in Debug builds. The active test files are `common/test/state_test.cpp` and `common/test/common_test.cpp`; others are disabled in CMakeLists.txt.

### Python Cython extension
```bash
cd python
make              # cython PyAppliFrame.pyx → .c → PyAppliFrame*.so
make install      # editable pip install
make test         # pytest, falls back to doctest
make clean
```
The `MCU_TARGET` variable (default `stm32l4xx`) controls which port include path is used.

### Log parser
```bash
cd python
python3 parse_logs.py   # reads log/*.txt, writes simulation/simulation_data.py
```

### Code quality (root Makefile)
```bash
make tidy     # clang-tidy on all C/C++ files (arm-none-eabi target, C11)
make format   # clang-format in-place
make check    # custom clang plugin (requires libShortIfReturnCheck.so)
make zip      # package sources
```

## Key data structures

All three layers share the same three structures (52 bytes total on wire):

| Layer | Name | Size | Contains |
|---|---|---|---|
| C header | `AppliFrame_t` | 52 B | header (8 B) + payload |
| C header | `payload_t` | 44 B | state + slot/hubCnt/init/conf |
| C header | `state_t` | 40 B | 16 key states (OFF/BLI/ON), dirty flag, labels |
| Python | `PyAppliFrame` / `Payload` / `State` | mirrors C | same fields |

The Python `simulation/` classes (`State.py`, `Payload.py`, `AppliFrame.py`) are pure-Python reimplementations for simulation; `PyAppliFrame.pyx` is the Cython bridge to the actual C code.

## Architecture: how the layers connect

```
STM32L476 firmware (Core/Src/)
    ↓ includes
lib/emLibC/common/   ← state.c, common.c, buffer.c, cycle.c …
    ↓ wrapped by
python/PyAppliFrame.pyx  (Cython, compiled to .so)
    ↓ used by
python/simulation/   ← radio_bell_test.py, simulation_data.py
python/trackDevice/  ← same structure, real-device variant
```

`python/simulation/` and `python/trackDevice/` are parallel trees with largely the same files; `simulation/` is the software-only path, `trackDevice/` connects to real serial devices via `RadioBellDevice.py`.

## Slot system

Slots are odd numbers 1–f (hex). Each device has a `my_slot` stored in EEPROM. Slot 1 acts as master when it wins arbitration (`Set me (1) as master`). The firmware cycle is 30 ms; sub-slot timing divides it into 16 sub-slots. Log files are named `slot_N.txt` by convention but the actual slot is in the `my_slot` EEPROM line—`slot_7.txt` currently contains a capture from slot 1.

## Important defines

| Define | Where | Purpose |
|---|---|---|
| `UNIT_TEST` | Cython build, CMake | excludes MCU-specific HAL code |
| `USE_HAL_DRIVER`, `STM32L476xx` | firmware + clang-tidy | STM32 HAL selection |
| `DEBUG` | CMake | enables ASAN in unit test builds |

## Generated files (do not edit by hand)

- `Core/Src/githash.c` / `Core/Inc/githash.h` — written by `preBuildScript.sh` at build time
- `python/simulation/simulation_data.py` — written by `python/parse_logs.py`
- `Debug/makefile`, `Debug/sources.mk`, `Debug/objects.mk` — STM32CubeIDE generated; do not edit
