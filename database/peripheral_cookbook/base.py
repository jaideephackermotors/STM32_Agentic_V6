"""Base class for all peripheral cookbook recipes."""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pydantic import BaseModel

from schemas.mcu_profile import MCUProfile


@dataclass
class PeripheralCode:
    """Generated C code for a single peripheral."""
    # MX_xxx_Init() function body (called from main)
    init_function: str = ""
    # Code for HAL_xxx_MspInit() (GPIO + clock enable, called by HAL internally)
    msp_init: str = ""
    # IRQ handler bodies for stm32f4xx_it.c
    irq_handlers: dict[str, str] = field(default_factory=dict)
    # HAL .c source files needed
    hal_sources: list[str] = field(default_factory=list)
    # HAL modules to enable in hal_conf.h
    hal_modules: list[str] = field(default_factory=list)
    # Private variable declarations for main.c (handles)
    handle_declarations: list[str] = field(default_factory=list)
    # #include directives needed
    includes: list[str] = field(default_factory=list)
    # Forward declaration of the init function
    init_prototype: str = ""


class CookbookRecipe(ABC):
    """Abstract base for peripheral cookbook recipes."""

    def __init__(self, mcu: MCUProfile):
        self.mcu = mcu

    @abstractmethod
    def generate(self, config: BaseModel) -> PeripheralCode:
        """Generate all C code for the peripheral from its config."""
        ...

    def _find_peripheral(self, instance_name: str):
        """Look up a PeripheralInstance by name."""
        for p in self.mcu.peripherals:
            if p.name == instance_name:
                return p
        raise ValueError(f"Peripheral {instance_name} not found in MCU profile")

    def _gpio_port_rcc(self, pin: str) -> str:
        """RCC enable macro for a pin's GPIO port."""
        from database.mcu.stm32f446re import GPIO_PORT_RCC
        port = pin[1]
        return GPIO_PORT_RCC.get(port, f"__HAL_RCC_GPIO{port}_CLK_ENABLE")

    def _pin_port_macro(self, pin: str) -> str:
        """GPIO port macro. PA5 → GPIOA"""
        return f"GPIO{pin[1]}"

    def _pin_number_macro(self, pin: str) -> str:
        """GPIO pin macro. PA5 → GPIO_PIN_5"""
        return f"GPIO_PIN_{int(pin[2:])}"
