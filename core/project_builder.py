"""Project directory scaffolder — creates the complete project structure."""

from __future__ import annotations
import logging
from pathlib import Path

from hal_manager.cache import HALCache
from hal_manager.downloader import HALDownloader
from hal_manager.extractor import HALExtractor
from schemas.blueprint import ProjectBlueprint

log = logging.getLogger(__name__)


class ProjectBuilder:
    """Creates the project directory structure and populates it with HAL files."""

    def __init__(self, hal_cache_dir: str = "~/.stm32_hal_cache"):
        self.cache = HALCache(hal_cache_dir)
        self.downloader = HALDownloader(self.cache)

    def build(self, blueprint: ProjectBlueprint, output_dir: str) -> Path:
        """Scaffold a complete project directory from a blueprint.

        Steps:
        1. Create directory structure
        2. Download HAL if not cached
        3. Extract needed HAL/CMSIS files
        4. Return project root path

        Code files (main.c, etc.) are NOT created here — that's the
        peripheral engine + template system's job.
        """
        project_dir = Path(output_dir) / blueprint.project_name
        project_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (project_dir / "Core" / "Src").mkdir(parents=True, exist_ok=True)
        (project_dir / "Core" / "Inc").mkdir(parents=True, exist_ok=True)
        (project_dir / "startup").mkdir(parents=True, exist_ok=True)

        # Ensure HAL drivers are available
        family = blueprint.family
        self.downloader.ensure_available(family)

        # Determine peripheral types from blueprint
        peripheral_types = self._collect_peripheral_types(blueprint)

        # Extract HAL files into project
        extractor = HALExtractor(self.cache, family)
        extractor.extract(project_dir, peripheral_types)

        log.info("Project scaffolded at %s", project_dir)
        return project_dir

    def _collect_peripheral_types(self, bp: ProjectBlueprint) -> list[str]:
        """Collect unique peripheral types from blueprint for HAL extraction."""
        types = set()
        if bp.uarts:
            types.add("uart")
        if bp.spis:
            types.add("spi")
        if bp.i2cs:
            types.add("i2c")
        if bp.timers:
            types.add("timer")
        if bp.adcs:
            types.add("adc")
        if bp.dmas:
            types.add("dma")
        return sorted(types)
