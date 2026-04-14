"""MCU hardware profile models — the ground truth for a specific MCU."""

from __future__ import annotations
from pydantic import BaseModel


class PinAF(BaseModel):
    """One alternate-function mapping for a GPIO pin."""
    pin: str          # e.g. "PA0"
    af: int           # AF number 0-15
    peripheral: str   # e.g. "TIM5_CH1", "USART2_TX"


class PeripheralInstance(BaseModel):
    """A peripheral instance on the MCU."""
    name: str              # e.g. "TIM5", "USART2", "ADC1"
    type: str              # "timer", "uart", "spi", "i2c", "adc", "dac", "dma"
    bus: str               # "APB1", "APB2", "AHB1"
    rcc_macro: str         # e.g. "__HAL_RCC_TIM5_CLK_ENABLE"
    irq_names: list[str]   # e.g. ["TIM5_IRQn"]


class DMAMapping(BaseModel):
    """DMA stream/channel mapping for a peripheral request."""
    peripheral: str   # e.g. "USART2_TX"
    dma: int          # 1 or 2
    stream: int       # 0-7
    channel: int      # 0-7


class TimerInfo(BaseModel):
    """Timer-specific metadata."""
    name: str             # e.g. "TIM5"
    is_advanced: bool     # TIM1, TIM8
    is_32bit: bool        # TIM2, TIM5
    channels: int         # number of capture/compare channels
    bus: str              # APB1 or APB2


class MCUProfile(BaseModel):
    """Complete hardware profile for a specific MCU."""
    name: str                  # e.g. "STM32F446RETx"
    family: str                # e.g. "stm32f4"
    core: str                  # e.g. "cortex-m4"
    fpu: bool
    flash_size_kb: int
    sram_size_kb: int
    flash_base: int            # 0x08000000
    sram_base: int             # 0x20000000
    max_sysclk_mhz: int       # 180 for F446
    max_apb1_mhz: int         # 45
    max_apb2_mhz: int         # 90
    hse_default_mhz: int      # 8 for NUCLEO boards
    gpio_ports: list[str]      # ["A", "B", "C", "D", "E", "H"]
    pin_af_table: list[PinAF]
    peripherals: list[PeripheralInstance]
    dma_mappings: list[DMAMapping]
    timers: list[TimerInfo]
