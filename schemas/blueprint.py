"""ProjectBlueprint — output of the architect agent, input to code generation."""

from __future__ import annotations
from pydantic import BaseModel

from schemas.peripheral_config import (
    ClockConfig,
    GPIOConfig,
    UARTConfig,
    SPIConfig,
    I2CConfig,
    TimerConfig,
    ADCConfig,
    DMAConfig,
)


class ProjectBlueprint(BaseModel):
    """Complete project specification — the single source of truth.

    Produced by the architect agent from RequirementSpec + MCU profile.
    Consumed by all deterministic engines (clock, GPIO, peripheral, etc.).
    """
    project_name: str
    mcu: str                            # e.g. "STM32F446RETx"
    family: str = "stm32f4"

    clock: ClockConfig
    gpios: list[GPIOConfig] = []
    uarts: list[UARTConfig] = []
    spis: list[SPIConfig] = []
    i2cs: list[I2CConfig] = []
    timers: list[TimerConfig] = []
    adcs: list[ADCConfig] = []
    dmas: list[DMAConfig] = []

    # HAL modules to enable in hal_conf.h (auto-populated by peripheral engine)
    hal_modules: list[str] = []

    # IRQ handlers needed (auto-populated by peripheral engine)
    irq_handlers: list[str] = []

    # Source files needed in Makefile (auto-populated)
    hal_sources: list[str] = []
