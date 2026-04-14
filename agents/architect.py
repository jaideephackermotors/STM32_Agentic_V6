"""Architect Agent — converts RequirementSpec into ProjectBlueprint.

This agent bridges the gap between parsed requirements and
the deterministic code generation engines. It resolves ambiguities,
assigns specific pins, calculates timer prescalers, and produces
a fully specified ProjectBlueprint.
"""

from __future__ import annotations
import json
import logging

from agents.agent_base import DeepSeekClient
from agents.failure_log import FailureLog
from schemas.requirements import RequirementSpec
from schemas.blueprint import ProjectBlueprint
from schemas.peripheral_config import (
    ClockConfig, GPIOConfig, UARTConfig, SPIConfig, I2CConfig,
    TimerConfig, TimerChannelConfig, ADCConfig, ADCChannelConfig,
)
from schemas.mcu_profile import MCUProfile
from core.clock_engine import ClockEngine

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert STM32 hardware architect. Given parsed requirements,
produce a complete ProjectBlueprint JSON.

MCU: {mcu_name} (max SYSCLK={max_sysclk}MHz, APB1 max={max_apb1}MHz, APB2 max={max_apb2}MHz)

You must produce a JSON object with these fields:
{{
  "project_name": "from requirements",
  "mcu": "{mcu_name}",
  "gpios": [  // standalone GPIO pins (LEDs, buttons)
    {{"pin": "PA5", "mode": "output_pp", "label": "LED", "speed": "low", "initial_state": "low"}}
  ],
  "uarts": [
    {{"instance": "USART2", "baud_rate": 115200, "word_length": 8, "stop_bits": 1,
      "parity": "none", "mode": "tx_rx", "tx_pin": "PA2", "rx_pin": "PA3",
      "interrupt": false, "dma_tx": false, "dma_rx": false}}
  ],
  "spis": [...],
  "i2cs": [...],
  "timers": [
    {{"instance": "TIM2", "mode": "basic|pwm|input_capture",
      "prescaler": 89, "period": 999,
      "channels": [{{"channel": 1, "pin": "PA0", "mode": "pwm", "polarity": "rising", "pulse": 500}}],
      "interrupt": true}}
  ],
  "adcs": [...],
  "dmas": []
}}

PIN ASSIGNMENT TABLE (valid AF mappings):
{pin_af_summary}

RULES:
1. Use ONLY pins with valid AF for the peripheral (from table above).
2. For timers: prescaler and period must produce the requested frequency.
   Formula: freq = timer_clk / ((prescaler + 1) * (period + 1))
   APB1 timer clock = {apb1_timer_mhz}MHz, APB2 timer clock = {apb2_timer_mhz}MHz
3. No pin conflicts — each pin used at most once.
4. Return ONLY the JSON. No markdown, no explanation.
"""


class ArchitectAgent:
    """Produces ProjectBlueprint from RequirementSpec + MCU profile."""

    def __init__(self, client: DeepSeekClient, mcu: MCUProfile):
        self.client = client
        self.mcu = mcu
        self.clock_engine = ClockEngine(mcu)
        self.failure_log = FailureLog("architect")

    def design(self, spec: RequirementSpec) -> ProjectBlueprint:
        """Design the complete project blueprint."""
        # First: solve the clock tree deterministically
        clock = self.clock_engine.solve(spec.target_sysclk_mhz)

        # Build pin-AF summary for the LLM
        af_summary = self._build_af_summary()

        # Inject past failure lessons into the prompt
        failures_section = self.failure_log.get_prompt_section()

        system = SYSTEM_PROMPT.format(
            mcu_name=self.mcu.name,
            max_sysclk=self.mcu.max_sysclk_mhz,
            max_apb1=self.mcu.max_apb1_mhz,
            max_apb2=self.mcu.max_apb2_mhz,
            pin_af_summary=af_summary,
            apb1_timer_mhz=clock.apb1_timer_mhz,
            apb2_timer_mhz=clock.apb2_timer_mhz,
        )
        if failures_section:
            system += "\n" + failures_section

        user_msg = f"RequirementSpec:\n{spec.model_dump_json(indent=2)}"

        def _inject_and_normalize(data: dict) -> None:
            """Inject clock config and normalize LLM outputs."""
            data["clock"] = clock.model_dump()
            data["mcu"] = self.mcu.name
            if "project_name" not in data:
                data["project_name"] = spec.project_name
            self._normalize_blueprint_data(data)

        data = self.client.reason_json_validated(
            system, user_msg,
            model_class=ProjectBlueprint,
            normalize_fn=_inject_and_normalize,
        )

        # Final construction (already validated inside reason_json_validated)
        _inject_and_normalize(data)

        try:
            blueprint = ProjectBlueprint(**data)
        except Exception as e:
            # Record the failure for future prompt enrichment
            self.failure_log.record_validation_error(str(e), data)
            raise

        blueprint = ProjectBlueprint(**data)
        log.info("Blueprint designed: %d gpios, %d uarts, %d timers, %d adcs",
                 len(blueprint.gpios), len(blueprint.uarts),
                 len(blueprint.timers), len(blueprint.adcs))
        return blueprint

    @staticmethod
    def _normalize_blueprint_data(data: dict) -> None:
        """Normalize common LLM abbreviations before pydantic validation."""
        # Normalize GPIO modes
        for gpio in data.get("gpios", []):
            GPIOConfig.normalize_mode(gpio)

        # Normalize timer modes
        TIMER_MODE_ALIASES = {
            "pwm_generation": "pwm", "PWM": "pwm", "Basic": "basic",
            "input-capture": "input_capture", "output-compare": "output_compare",
        }
        for tim in data.get("timers", []):
            if isinstance(tim, dict) and "mode" in tim:
                tim["mode"] = TIMER_MODE_ALIASES.get(tim["mode"], tim["mode"])
            for ch in tim.get("channels", []) if isinstance(tim, dict) else []:
                if isinstance(ch, dict) and "mode" in ch:
                    ch["mode"] = TIMER_MODE_ALIASES.get(ch["mode"], ch["mode"])

        # Normalize UART fields
        UART_MODE_ALIASES = {
            "tx": "tx_only", "rx": "rx_only", "txrx": "tx_rx",
            "TX_RX": "tx_rx", "tx/rx": "tx_rx",
        }
        UART_PIN_ALIASES = {
            "tx": "tx_pin", "TX": "tx_pin", "TX_Pin": "tx_pin",
            "rx": "rx_pin", "RX": "rx_pin", "RX_Pin": "rx_pin",
        }
        for uart in data.get("uarts", []):
            if isinstance(uart, dict):
                for alias, canonical in UART_PIN_ALIASES.items():
                    if alias in uart and canonical not in uart:
                        uart[canonical] = uart.pop(alias)
                if "mode" in uart:
                    uart["mode"] = UART_MODE_ALIASES.get(uart["mode"], uart["mode"])

        # Normalize I2C pin fields
        I2C_PIN_ALIASES = {
            "scl": "scl_pin", "SCL": "scl_pin", "SCL_Pin": "scl_pin",
            "sda": "sda_pin", "SDA": "sda_pin", "SDA_Pin": "sda_pin",
        }
        for i2c in data.get("i2cs", []):
            if isinstance(i2c, dict):
                for alias, canonical in I2C_PIN_ALIASES.items():
                    if alias in i2c and canonical not in i2c:
                        i2c[canonical] = i2c.pop(alias)

        # Normalize SPI fields
        SPI_PIN_ALIASES = {
            "mosi": "mosi_pin", "MOSI": "mosi_pin", "MOSI_Pin": "mosi_pin",
            "miso": "miso_pin", "MISO": "miso_pin", "MISO_Pin": "miso_pin",
            "sck": "sck_pin", "SCK": "sck_pin", "SCK_Pin": "sck_pin", "clk_pin": "sck_pin",
            "nss": "nss_pin", "NSS": "nss_pin", "NSS_Pin": "nss_pin", "cs_pin": "nss_pin",
            "cs": "nss_pin", "CS": "nss_pin",
        }
        for spi in data.get("spis", []):
            if isinstance(spi, dict):
                # Remap aliased pin field names
                for alias, canonical in SPI_PIN_ALIASES.items():
                    if alias in spi and canonical not in spi:
                        spi[canonical] = spi.pop(alias)
                if "mode" in spi:
                    spi["mode"] = spi["mode"].lower()
                # Normalize nss_pin: "None"/"none"/""  → None
                if "nss_pin" in spi and spi["nss_pin"] in ("None", "none", "null", ""):
                    spi["nss_pin"] = None
                # Normalize cpol: "low"/"high" → 0/1
                CPOL_ALIASES = {"low": 0, "LOW": 0, "high": 1, "HIGH": 1, "0": 0, "1": 1}
                if "cpol" in spi and not isinstance(spi["cpol"], int):
                    spi["cpol"] = CPOL_ALIASES.get(str(spi["cpol"]), 0)
                # Normalize cpha: "1edge"/"2edge" → 0/1
                CPHA_ALIASES = {"1edge": 0, "2edge": 1, "1Edge": 0, "2Edge": 1,
                                "first": 0, "second": 1, "0": 0, "1": 1}
                if "cpha" in spi and not isinstance(spi["cpha"], int):
                    spi["cpha"] = CPHA_ALIASES.get(str(spi["cpha"]), 0)
                # Normalize first_bit: case insensitive
                if "first_bit" in spi:
                    spi["first_bit"] = str(spi["first_bit"]).lower()

        # Normalize ADC resolution (LLM may return "12bit" instead of 12)
        import re as _re
        for adc in data.get("adcs", []):
            if isinstance(adc, dict) and "resolution" in adc:
                res = adc["resolution"]
                if isinstance(res, str):
                    digits = _re.findall(r'\d+', str(res))
                    if digits:
                        adc["resolution"] = int(digits[0])

            # Normalize ADC channel configs
            for ch in adc.get("channels", []) if isinstance(adc, dict) else []:
                if isinstance(ch, dict):
                    if "sampling_time" in ch and isinstance(ch["sampling_time"], str):
                        digits = _re.findall(r'\d+', ch["sampling_time"])
                        if digits:
                            ch["sampling_time"] = int(digits[0])

        # Normalize DMA direction
        DMA_DIR_ALIASES = {
            "memory_to_peripheral": "memory_to_periph",
            "peripheral_to_memory": "periph_to_memory",
            "mem_to_periph": "memory_to_periph",
            "periph_to_mem": "periph_to_memory",
        }
        for dma in data.get("dmas", []):
            if isinstance(dma, dict) and "direction" in dma:
                dma["direction"] = DMA_DIR_ALIASES.get(dma["direction"], dma["direction"])

        # Normalize GPIO speed
        SPEED_ALIASES = {"very high": "very_high", "veryHigh": "very_high", "VeryHigh": "very_high"}
        for gpio in data.get("gpios", []):
            if isinstance(gpio, dict) and "speed" in gpio:
                gpio["speed"] = SPEED_ALIASES.get(gpio["speed"], gpio["speed"])

    def _build_af_summary(self) -> str:
        """Build a compact pin-AF table for the system prompt."""
        lines = []
        # Group by peripheral
        from collections import defaultdict
        by_periph: dict[str, list[str]] = defaultdict(list)
        for af in self.mcu.pin_af_table:
            by_periph[af.peripheral].append(f"{af.pin}(AF{af.af})")

        for periph in sorted(by_periph.keys()):
            pins = ", ".join(by_periph[periph])
            lines.append(f"  {periph}: {pins}")

        return "\n".join(lines)
