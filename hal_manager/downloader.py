"""Download STM32 HAL libraries from GitHub using sparse checkout."""

from __future__ import annotations
import subprocess
import logging
from pathlib import Path

from hal_manager.cache import HALCache

log = logging.getLogger(__name__)

# Map family shortname → GitHub repo URL
FAMILY_REPOS: dict[str, str] = {
    "stm32f4": "https://github.com/STMicroelectronics/STM32CubeF4.git",
}


class HALDownloader:
    """Downloads STM32Cube repos with sparse checkout (Drivers/ only)."""

    def __init__(self, cache: HALCache):
        self.cache = cache

    def ensure_available(self, family: str) -> Path:
        """Ensure HAL drivers for the given family are cached locally.

        Uses git sparse-checkout to download only the Drivers/ directory,
        which is ~200MB instead of ~2GB for the full repo.

        Returns path to the cached family directory.
        """
        if self.cache.is_cached(family):
            log.info("HAL cache hit for %s", family)
            return self.cache.family_dir(family)

        repo_url = FAMILY_REPOS.get(family)
        if not repo_url:
            raise ValueError(f"Unknown MCU family: {family}. Supported: {list(FAMILY_REPOS.keys())}")

        dest = self.cache.family_dir(family)
        dest.mkdir(parents=True, exist_ok=True)

        log.info("Downloading HAL drivers for %s (sparse checkout)...", family)

        # Clone with blob filter and no checkout (fast, minimal download)
        subprocess.run(
            ["git", "clone", "--filter=blob:none", "--no-checkout", "--depth=1",
             repo_url, "."],
            cwd=str(dest), check=True, capture_output=True,
            timeout=600,
        )

        # Set up cone-mode sparse checkout for Drivers/ only
        subprocess.run(
            ["git", "sparse-checkout", "init", "--cone"],
            cwd=str(dest), check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "sparse-checkout", "set", "Drivers/STM32F4xx_HAL_Driver",
             "Drivers/CMSIS"],
            cwd=str(dest), check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "checkout"],
            cwd=str(dest), check=True, capture_output=True,
            timeout=600,
        )

        # HAL_Driver and CMSIS/Device are git submodules — init them
        subprocess.run(
            ["git", "submodule", "update", "--init", "--depth=1",
             "Drivers/STM32F4xx_HAL_Driver",
             "Drivers/CMSIS/Device/ST/STM32F4xx"],
            cwd=str(dest), check=True, capture_output=True,
            timeout=600,
        )

        log.info("HAL drivers cached at %s", dest)
        return dest
