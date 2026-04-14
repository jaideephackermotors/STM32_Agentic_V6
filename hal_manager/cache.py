"""Local cache for STM32 HAL libraries downloaded from GitHub."""

from __future__ import annotations
from pathlib import Path


class HALCache:
    """Manages a local cache directory for STM32Cube repositories."""

    def __init__(self, cache_dir: str = "~/.stm32_hal_cache"):
        self.cache_dir = Path(cache_dir).expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def family_dir(self, family: str) -> Path:
        """Return the cached repo path for a given family (e.g. 'stm32f4')."""
        return self.cache_dir / family

    def is_cached(self, family: str) -> bool:
        """Check if a family's HAL drivers are already cached."""
        d = self.family_dir(family)
        # Check for the Drivers directory which is what we need
        return (d / "Drivers").is_dir()

    def hal_driver_dir(self, family: str) -> Path:
        """Path to HAL driver sources: Drivers/STM32F4xx_HAL_Driver/."""
        family_upper = family.upper().replace("STM32", "STM32")
        # stm32f4 → STM32F4xx
        tag = family.replace("stm32", "STM32").replace("f4", "F4xx")
        return self.family_dir(family) / "Drivers" / f"{tag}_HAL_Driver"

    def cmsis_device_dir(self, family: str) -> Path:
        """Path to CMSIS device headers: Drivers/CMSIS/Device/ST/STM32F4xx/."""
        tag = family.replace("stm32", "STM32").replace("f4", "F4xx")
        return self.family_dir(family) / "Drivers" / "CMSIS" / "Device" / "ST" / tag

    def cmsis_core_dir(self, family: str) -> Path:
        """Path to CMSIS core headers: Drivers/CMSIS/Include/."""
        return self.family_dir(family) / "Drivers" / "CMSIS" / "Include"
