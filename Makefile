all: tidy

PLUGIN = ./libShortIfReturnCheck.so
CLANG = clang

BN := $(notdir $(CURDIR))

zip:
	@echo "target is $(BN)"
	zip -r "$(BN).zip" .  -i '*.c' '*.cc' '*.py' '*.md' '*.h' '*.ld' '*.ioc' '*.tex' \
	     'Makefile' '.clang*' '.gitmodules'

clean:
	rm "$(BN).zip"

	
check:
	@echo "Running Clang plugin checks..."
	@find . -iregex '.*\.\(c\|cpp\|h\)' | while read f; do \
		$(CLANG) -Xclang -load -Xclang $(PLUGIN) \
		-Xclang -plugin -Xclang short-if-return-check \
		-fsyntax-only $$f; \
	done

format: 
	@echo "Running clang-format..."
	find . -iregex '.*\.\(c\|h|cpp|py\)'| xargs clang-format -i

print-%  : ; @echo $* = $($*)

SOURCES := $(shell find . -type f -iregex '.*\.\(c\|cpp\)')
INC := $(shell find . -type d \( -iname 'inc' -o -iname 'inc*' \))
INCLUDES := $(addprefix -I,$(INC))

DEFS := -DUSE_HAL_DRIVER -DSTM32L476xx -D__GNUC__ -D__ARM_ARCH_7EM__

CSTD := -std=c11
TARGET := -target arm-none-eabi

tidy:
	@for src in $(SOURCES); do \
		echo "Running clang-tidy on $$src..."; \
		clang-tidy $$src -- $(CSTD) $(TARGET) $(DEFS) $(INCLUDES) ; \
	done
	@echo "Done"

print-INCLUDES:
	@echo $(INCLUDES)
	
