"""Per-peripheral configuration models used in ProjectBlueprint."""

from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel


class ClockConfig(BaseModel):
    """Complete clock tree configuration."""
    hse_mhz: int = 8
    pll_m: int
    pll_n: int
    pll_p: int       # 2, 4, 6, or 8
    pll_q: int = 4   # for USB, typically 4
    ahb_prescaler: int = 1
    apb1_prescaler: int = 4
    apb2_prescaler: int = 2
    # Derived (computed by clock engine, stored for reference)
    sysclk_mhz: int = 0
    hclk_mhz: int = 0
    apb1_mhz: int = 0
    apb2_mhz: int = 0
    apb1_timer_mhz: int = 0
    apb2_timer_mhz: int = 0


class GPIOConfig(BaseModel):
    """Standalone GPIO pin configuration (not driven by a peripheral)."""
    pin: str              # e.g. "PA5"
    mode: Literal["output_pp", "output_od", "input", "input_pullup", "input_pulldown", "analog"]
    label: str = ""       # e.g. "LED", "BUTTON"
    speed: Literal["low", "medium", "high", "very_high"] = "low"
    initial_state: Literal["high", "low"] = "low"

    @classmethod
    def normalize_mode(cls, data: dict) -> dict:
        """Normalize common LLM abbreviations for GPIO mode before validation."""
        MODE_ALIASES = {
            "input_pu": "input_pullup",
            "input_pd": "input_pulldown",
            "in_pu": "input_pullup",
            "in_pd": "input_pulldown",
            "pp": "output_pp",
            "od": "output_od",
            "push_pull": "output_pp",
            "open_drain": "output_od",
            "output": "output_pp",
            "output_pushpull": "output_pp",
            "output_opendrain": "output_od",
            "input_pull_up": "input_pullup",
            "input_pull_down": "input_pulldown",
        }
        if isinstance(data, dict) and "mode" in data:
            data["mode"] = MODE_ALIASES.get(data["mode"], data["mode"])
        return data


class UARTConfig(BaseModel):
    """UART/USART peripheral configuration."""
    instance: str         # e.g. "USART2"
    baud_rate: int = 115200
    word_length: Literal[8, 9] = 8
    stop_bits: Literal[1, 2] = 1
    parity: Literal["none", "even", "odd"] = "none"
    mode: Literal["tx_rx", "tx_only", "rx_only"] = "tx_rx"
    tx_pin: Optional[str] = None    # e.g. "PA2", None for rx_only
    rx_pin: Optional[str] = None    # e.g. "PA3", None for tx_only
    interrupt: bool = False
    dma_tx: bool = False
    dma_rx: bool = False


class SPIConfig(BaseModel):
    """SPI peripheral configuration."""
    instance: str         # e.g. "SPI1"
    mode: Literal["master", "slave"] = "master"
    baud_prescaler: int = 16
    cpol: Literal[0, 1] = 0
    cpha: Literal[0, 1] = 0
    data_size: Literal[8, 16] = 8
    first_bit: Literal["msb", "lsb"] = "msb"
    sck_pin: str
    mosi_pin: str
    miso_pin: str
    nss_pin: Optional[str] = None
    interrupt: bool = False
    dma_tx: bool = False
    dma_rx: bool = False


class I2CConfig(BaseModel):
    """I2C peripheral configuration."""
    instance: str         # e.g. "I2C1"
    clock_speed: int = 100000   # 100kHz standard, 400kHz fast
    duty_cycle: Literal["2", "16_9"] = "2"
    scl_pin: str
    sda_pin: str
    interrupt: bool = False
    dma_tx: bool = False
    dma_rx: bool = False


class TimerConfig(BaseModel):
    """Timer peripheral configuration."""
    instance: str         # e.g. "TIM2"
    mode: Literal["basic", "pwm", "input_capture", "output_compare", "encoder"]
    prescaler: int = 0
    period: int = 0xFFFF
    channels: list[TimerChannelConfig] = []
    interrupt: bool = False


class TimerChannelConfig(BaseModel):
    """Configuration for a single timer channel."""
    channel: int          # 1-4
    pin: str              # e.g. "PA0"
    mode: Literal["pwm", "input_capture", "output_compare"] = "pwm"
    polarity: Literal["rising", "falling", "both"] = "rising"
    pulse: int = 0        # for PWM: compare value (duty cycle)
    ic_filter: int = 0    # input capture filter


class ADCConfig(BaseModel):
    """ADC peripheral configuration."""
    instance: str         # e.g. "ADC1"
    resolution: Literal[6, 8, 10, 12] = 12
    channels: list[ADCChannelConfig] = []
    continuous: bool = False
    scan: bool = False
    interrupt: bool = False
    dma: bool = False


class ADCChannelConfig(BaseModel):
    """Configuration for a single ADC channel."""
    channel: int          # 0-18
    pin: str              # e.g. "PA0" (or "internal" for temp/vref)
    rank: int = 1
    sampling_time: int = 84   # cycles: 3, 15, 28, 56, 84, 112, 144, 480


class DMAConfig(BaseModel):
    """DMA stream configuration."""
    dma: int              # 1 or 2
    stream: int           # 0-7
    channel: int          # 0-7
    direction: Literal["periph_to_memory", "memory_to_periph", "memory_to_memory"]
    periph_data_size: Literal["byte", "halfword", "word"] = "byte"
    mem_data_size: Literal["byte", "halfword", "word"] = "byte"
    circular: bool = False
    priority: Literal["low", "medium", "high", "very_high"] = "low"


# Fix forward reference for TimerConfig
TimerConfig.model_rebuild()
