"""Startup file manager — ensures correct startup_*.s is in the project."""

from __future__ import annotations
import shutil
import logging
from pathlib import Path

from hal_manager.cache import HALCache

log = logging.getLogger(__name__)

# Map MCU → startup file name
STARTUP_FILES = {
    "STM32F446RETx": "startup_stm32f446xx.s",
}


class StartupManager:
    """Copies the correct startup assembly file into the project."""

    def __init__(self, cache: HALCache, family: str = "stm32f4"):
        self.cache = cache
        self.family = family

    def ensure_startup(self, project_dir: Path, mcu_name: str) -> None:
        """Copy startup file if not already present."""
        filename = STARTUP_FILES.get(mcu_name)
        if not filename:
            raise ValueError(f"No startup file mapping for {mcu_name}")

        dst = project_dir / "startup" / filename
        if dst.is_file():
            return

        # Try to copy from cache
        dev_src = self.cache.cmsis_device_dir(self.family)
        src = dev_src / "Source" / "Templates" / "gcc" / filename
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            log.info("Copied startup file: %s", dst)
        else:
            log.warning("Startup file not found in cache: %s", src)

    def get_startup_filename(self, mcu_name: str) -> str:
        """Return the startup filename for a given MCU."""
        return STARTUP_FILES.get(mcu_name, "startup_stm32f446xx.s")
