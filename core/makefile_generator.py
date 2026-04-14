"""Makefile generator for STM32 projects using arm-none-eabi-gcc."""

from __future__ import annotations
from pathlib import Path

from schemas.blueprint import ProjectBlueprint


class MakefileGenerator:
    """Generates a GCC Makefile for the STM32 project."""

    def generate(self, blueprint: ProjectBlueprint, hal_sources: list[str]) -> str:
        """Generate complete Makefile content."""
        project = blueprint.project_name
        mcu_lower = "stm32f446xx"
        mcu_define = "STM32F446xx"

        # Collect all C sources
        c_sources = [
            "Core/Src/main.c",
            "Core/Src/stm32f4xx_it.c",
            "Core/Src/stm32f4xx_hal_msp.c",
            "Core/Src/system_stm32f4xx.c",
        ]
        for src in hal_sources:
            c_sources.append(f"Drivers/STM32F4xx_HAL_Driver/Src/{src}")

        sources_block = " \\\n".join(c_sources)

        # Include paths
        inc_paths = [
            "Core/Inc",
            "Drivers/STM32F4xx_HAL_Driver/Inc",
            "Drivers/CMSIS/Include",
            "Drivers/CMSIS/Device/ST/STM32F4xx/Include",
        ]
        includes_block = " ".join(f"-I{p}" for p in inc_paths)

        return f"""\
######################################
# target
######################################
TARGET = {project}

######################################
# building variables
######################################
DEBUG = 1
OPT = -Og

#######################################
# paths
#######################################
BUILD_DIR = build

######################################
# source
######################################
C_SOURCES = \\
{sources_block}

ASM_SOURCES = \\
startup/{mcu_lower}.s

#######################################
# binaries
#######################################
PREFIX = arm-none-eabi-
CC = $(PREFIX)gcc
AS = $(PREFIX)gcc -x assembler-with-cpp
CP = $(PREFIX)objcopy
SZ = $(PREFIX)size
HEX = $(CP) -O ihex
BIN = $(CP) -O binary -S

#######################################
# CFLAGS
#######################################
CPU = -mcpu=cortex-m4
FPU = -mfpu=fpv4-sp-d16
FLOAT-ABI = -mfloat-abi=hard
MCU = $(CPU) -mthumb $(FPU) $(FLOAT-ABI)

C_DEFS = \\
-D{mcu_define} \\
-DUSE_HAL_DRIVER

C_INCLUDES = \\
{includes_block}

CFLAGS = $(MCU) $(C_DEFS) $(C_INCLUDES) $(OPT) -Wall -Wextra -Werror -Wshadow \\
-fdata-sections -ffunction-sections -fstack-usage -fno-common

ifeq ($(DEBUG), 1)
CFLAGS += -g -gdwarf-2
endif

CFLAGS += -MMD -MP -MF"$(@:%.o=%.d)"

#######################################
# LDFLAGS
#######################################
LDSCRIPT = STM32F446RETx_FLASH.ld

LIBS = -lc -lm -lnosys
LIBDIR =
LDFLAGS = $(MCU) -specs=nano.specs -T$(LDSCRIPT) $(LIBDIR) $(LIBS) \\
-Wl,-Map=$(BUILD_DIR)/$(TARGET).map,--cref -Wl,--gc-sections -Wl,--fatal-warnings

#######################################
# build the application
#######################################
all: $(BUILD_DIR)/$(TARGET).elf $(BUILD_DIR)/$(TARGET).hex $(BUILD_DIR)/$(TARGET).bin

OBJECTS = $(addprefix $(BUILD_DIR)/,$(notdir $(C_SOURCES:.c=.o)))
vpath %.c $(sort $(dir $(C_SOURCES)))

OBJECTS += $(addprefix $(BUILD_DIR)/,$(notdir $(ASM_SOURCES:.s=.o)))
vpath %.s $(sort $(dir $(ASM_SOURCES)))

$(BUILD_DIR)/%.o: %.c Makefile | $(BUILD_DIR)
\t$(CC) -c $(CFLAGS) -Wa,-a,-ad,-alms=$(BUILD_DIR)/$(notdir $(<:.c=.lst)) $< -o $@

$(BUILD_DIR)/%.o: %.s Makefile | $(BUILD_DIR)
\t$(AS) -c $(CFLAGS) $< -o $@

$(BUILD_DIR)/$(TARGET).elf: $(OBJECTS) Makefile
\t$(CC) $(OBJECTS) $(LDFLAGS) -o $@
\t$(SZ) $@

$(BUILD_DIR)/%.hex: $(BUILD_DIR)/%.elf | $(BUILD_DIR)
\t$(HEX) $< $@

$(BUILD_DIR)/%.bin: $(BUILD_DIR)/%.elf | $(BUILD_DIR)
\t$(BIN) $< $@

$(BUILD_DIR):
\tmkdir -p $@

#######################################
# clean up
#######################################
clean:
\t-rm -fR $(BUILD_DIR)

#######################################
# dependencies
#######################################
-include $(wildcard $(BUILD_DIR)/*.d)
"""
