"""GPIO cookbook — standalone GPIO pins (LEDs, buttons, etc.).

This is a thin wrapper since GPIOEngine handles the actual code gen.
Used when the peripheral_engine iterates over blueprint.gpios.
"""

from __future__ import annotations
from database.peripheral_cookbook.base import CookbookRecipe, PeripheralCode
from schemas.peripheral_config import GPIOConfig
from schemas.mcu_profile import MCUProfile
from core.gpio_engine import GPIOEngine


class GPIOCookbook(CookbookRecipe):
    """Generates MX_GPIO_Init() for standalone GPIOs."""

    def __init__(self, mcu: MCUProfile):
        super().__init__(mcu)
        self.engine = GPIOEngine(mcu)

    def generate(self, config: list[GPIOConfig]) -> PeripheralCode:
        """Generate GPIO init code for a list of standalone GPIOs."""
        code = self.engine.generate_standalone_init(config)
        return PeripheralCode(
            peripheral_type="gpio",
            init_function=code,
            init_prototype="static void MX_GPIO_Init(void);",
            hal_modules=["HAL_GPIO_MODULE_ENABLED"],
        )
