"""Pydantic schema models — typed contracts between all agents and engines."""

from schemas.mcu_profile import MCUProfile, PinAF, PeripheralInstance, DMAMapping, TimerInfo
from schemas.peripheral_config import (
    ClockConfig,
    GPIOConfig,
    UARTConfig,
    SPIConfig,
    I2CConfig,
    TimerConfig,
    TimerChannelConfig,
    ADCConfig,
    ADCChannelConfig,
    DMAConfig,
)
from schemas.requirements import RequirementSpec, PeripheralRequirement, PipelineResult
from schemas.blueprint import ProjectBlueprint

__all__ = [
    "MCUProfile", "PinAF", "PeripheralInstance", "DMAMapping", "TimerInfo",
    "ClockConfig", "GPIOConfig", "UARTConfig", "SPIConfig", "I2CConfig",
    "TimerConfig", "TimerChannelConfig", "ADCConfig", "ADCChannelConfig", "DMAConfig",
    "RequirementSpec", "PeripheralRequirement", "PipelineResult",
    "ProjectBlueprint",
]
