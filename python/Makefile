# ============================
# python/Makefile
# Cython-Build fuer PyAppliFrame Extension
# Aufruf: cd python && make
#         oder vom Root: make -C python
# ============================

PYTHON      ?= python3
PIP         ?= pip3
MCU_TARGET  ?= stm32l4xx

ROOT        := ..
LIB_ROOT    := $(ROOT)/lib/emLibC
COMMON_INC  := $(LIB_ROOT)/common/inc
PORT_INC    := $(LIB_ROOT)/port/src/stm/$(MCU_TARGET)

PYX         := PyAppliFrame.pyx
PYC         := PyAppliFrame.c
SO          := PyAppliFrame*.so
BUILD_DIR   := build

.PHONY: all build install clean test

# ============================
# Default
# ============================
all: build

# ============================
# Transpile .pyx -> .c
# ============================
$(PYC): $(PYX) state_decl.pxd common_decl.pxd payload_decl.pxd appliframe_decl.pxd
	@command -v cython >/dev/null 2>&1 || \
	    { echo "ERROR: cython nicht gefunden. pip install cython"; exit 1; }
	cython -3 -a -I . \
	    -E UNIT_TEST=1 \
	    $(PYX) \
	    --output-file $(PYC)

# ============================
# Kompiliert .c -> .so
# ============================
build: $(PYC)
	mkdir -p $(BUILD_DIR)
	MCU_TARGET=$(MCU_TARGET) \
	COMMON_INC=$(COMMON_INC) \
	PORT_INC=$(PORT_INC) \
	$(PYTHON) setup.py build_ext --inplace
	@echo "Extension gebaut -> $(SO)"
	@echo "from PyAppliFrame import PyState, PyPayload, PyAppliFrame, EmMsg, KeyState"

# ============================
# Editable pip install
# ============================
install: $(PYC)
	$(PIP) install -e .
	@echo "PyAppliFrame installiert (editable)"

# ============================
# Tests
# ============================
test: build
	$(PYTHON) -m pytest -v || $(PYTHON) -m doctest $(PYX) -v

# ============================
# Aufräumen
# ============================
clean:
	rm -f  $(PYC)
	rm -f  *.html
	rm -f  *.so
	rm -f  *.pyd
	rm -rf $(BUILD_DIR)
	rm -rf __pycache__
	rm -rf *.egg-info
	@echo "Python-Artefakte entfernt"

# ============================
# Help
# ============================
help:
	@echo ""
	@echo "Targets:"
	@echo "  all / build  – .pyx -> .c -> .so"
	@echo "  install      – editable pip install"
	@echo "  test         – pytest / doctest"
	@echo "  clean        – Artefakte loeschen"
	@echo ""
	@echo "Optionen:"
	@echo "  MCU_TARGET=stm32l4xx  (default)"
	@echo ""
