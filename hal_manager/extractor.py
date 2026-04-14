"""Extract needed HAL driver files from cache into a project directory."""

from __future__ import annotations
import shutil
import logging
from pathlib import Path

from hal_manager.cache import HALCache

log = logging.getLogger(__name__)

# HAL modules always needed regardless of peripherals
ALWAYS_NEEDED_HAL = [
    "stm32f4xx_hal.c",
    "stm32f4xx_hal_cortex.c",
    "stm32f4xx_hal_rcc.c",
    "stm32f4xx_hal_rcc_ex.c",
    "stm32f4xx_hal_gpio.c",
    "stm32f4xx_hal_pwr.c",
    "stm32f4xx_hal_pwr_ex.c",
    "stm32f4xx_hal_flash.c",
    "stm32f4xx_hal_flash_ex.c",
]

# Map peripheral type → additional HAL source files needed
PERIPHERAL_HAL_FILES: dict[str, list[str]] = {
    "uart": ["stm32f4xx_hal_uart.c"],
    "spi": ["stm32f4xx_hal_spi.c"],
    "i2c": ["stm32f4xx_hal_i2c.c", "stm32f4xx_hal_i2c_ex.c"],
    "timer": ["stm32f4xx_hal_tim.c", "stm32f4xx_hal_tim_ex.c"],
    "adc": ["stm32f4xx_hal_adc.c", "stm32f4xx_hal_adc_ex.c"],
    "dac": ["stm32f4xx_hal_dac.c", "stm32f4xx_hal_dac_ex.c"],
    "dma": ["stm32f4xx_hal_dma.c", "stm32f4xx_hal_dma_ex.c"],
    "can": ["stm32f4xx_hal_can.c"],
}


class HALExtractor:
    """Copies required HAL/CMSIS files from cache into a project."""

    def __init__(self, cache: HALCache, family: str = "stm32f4"):
        self.cache = cache
        self.family = family

    def extract(self, project_dir: Path, peripheral_types: list[str]) -> None:
        """Copy HAL drivers, CMSIS headers, and startup files into project_dir.

        Args:
            project_dir: Target project root directory.
            peripheral_types: List of peripheral types used (e.g. ["uart", "timer"]).
        """
        self._copy_cmsis_headers(project_dir)
        self._copy_hal_drivers(project_dir, peripheral_types)
        self._copy_startup_file(project_dir)
        log.info("HAL files extracted to %s", project_dir)

    def _copy_cmsis_headers(self, project_dir: Path) -> None:
        """Copy CMSIS core headers and device-specific headers."""
        cmsis_dst = project_dir / "Drivers" / "CMSIS"

        # Core CMSIS headers (core_cm4.h, cmsis_gcc.h, etc.)
        core_src = self.cache.cmsis_core_dir(self.family)
        core_dst = cmsis_dst / "Include"
        if core_src.is_dir():
            shutil.copytree(core_src, core_dst, dirs_exist_ok=True)

        # Device headers (stm32f4xx.h, stm32f446xx.h, system_stm32f4xx.h)
        dev_src = self.cache.cmsis_device_dir(self.family)
        dev_inc_src = dev_src / "Include"
        dev_inc_dst = cmsis_dst / "Device" / "ST" / "STM32F4xx" / "Include"
        if dev_inc_src.is_dir():
            shutil.copytree(dev_inc_src, dev_inc_dst, dirs_exist_ok=True)

        # System source template (system_stm32f4xx.c)
        sys_src = dev_src / "Source" / "Templates" / "system_stm32f4xx.c"
        sys_dst = project_dir / "Core" / "Src" / "system_stm32f4xx.c"
        if sys_src.is_file():
            sys_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sys_src, sys_dst)

    def _copy_hal_drivers(self, project_dir: Path, peripheral_types: list[str]) -> None:
        """Copy HAL driver .c and .h files."""
        hal_src_dir = self.cache.hal_driver_dir(self.family)
        hal_inc_src = hal_src_dir / "Inc"
        hal_src_src = hal_src_dir / "Src"

        hal_dst = project_dir / "Drivers" / "STM32F4xx_HAL_Driver"
        hal_inc_dst = hal_dst / "Inc"
        hal_src_dst = hal_dst / "Src"
        hal_inc_dst.mkdir(parents=True, exist_ok=True)
        hal_src_dst.mkdir(parents=True, exist_ok=True)

        # Copy ALL headers (they're small and needed for compilation)
        if hal_inc_src.is_dir():
            shutil.copytree(hal_inc_src, hal_inc_dst, dirs_exist_ok=True)

        # Copy only needed .c source files
        needed_sources = set(ALWAYS_NEEDED_HAL)
        for ptype in peripheral_types:
            needed_sources.update(PERIPHERAL_HAL_FILES.get(ptype, []))

        for src_name in needed_sources:
            src_file = hal_src_src / src_name
            if src_file.is_file():
                shutil.copy2(src_file, hal_src_dst / src_name)
            else:
                log.warning("HAL source not found: %s", src_file)

    def _copy_startup_file(self, project_dir: Path) -> None:
        """Copy the GCC startup assembly file."""
        dev_src = self.cache.cmsis_device_dir(self.family)
        startup_src = dev_src / "Source" / "Templates" / "gcc" / "startup_stm32f446xx.s"
        startup_dst = project_dir / "startup" / "startup_stm32f446xx.s"
        startup_dst.parent.mkdir(parents=True, exist_ok=True)

        if startup_src.is_file():
            shutil.copy2(startup_src, startup_dst)
        else:
            log.warning("Startup file not found: %s", startup_src)

    def get_hal_source_list(self, peripheral_types: list[str]) -> list[str]:
        """Return list of HAL .c filenames needed for the Makefile."""
        sources = set(ALWAYS_NEEDED_HAL)
        for ptype in peripheral_types:
            sources.update(PERIPHERAL_HAL_FILES.get(ptype, []))
        return sorted(sources)
