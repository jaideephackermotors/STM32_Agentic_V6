"""RequirementSpec — output of the requirement parser agent."""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class PeripheralRequirement(BaseModel):
    """A single peripheral requirement extracted from user text."""
    type: str              # "uart", "spi", "i2c", "timer", "adc", "gpio", "dma"
    instance: str          # e.g. "USART2", "TIM5", "ADC1", "PA5"
    purpose: str           # e.g. "serial output at 115200", "LED blink at 1Hz"
    parameters: dict       # type-specific params: {"baud_rate": 115200}, {"frequency_hz": 1}
    pins: list[str] = []   # suggested pins (may be empty if agent should pick)
    interrupt: bool = False
    dma: bool = False


class RequirementSpec(BaseModel):
    """Structured output from requirement parser agent."""
    project_name: str
    mcu: str                    # e.g. "STM32F446RETx"
    target_sysclk_mhz: int = 180
    peripherals: list[PeripheralRequirement]
    rtos: bool = False
    description: str = ""
    raw_text: str = ""          # original user requirements


class PipelineResult(BaseModel):
    """Final result from the orchestrator."""
    success: bool
    project_dir: Optional[str] = None
    elf_path: Optional[str] = None
    flash_size: int = 0
    ram_size: int = 0
    failed_stage: Optional[str] = None
    error: Optional[str] = None
    stages_completed: list[str] = []
    emulation_result: Optional[dict] = None
