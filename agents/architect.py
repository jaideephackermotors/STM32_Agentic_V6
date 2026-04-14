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

    def design(self, spec: RequirementSpec) -> ProjectBlueprint:
        """Design the complete project blueprint."""
        # First: solve the clock tree deterministically
        clock = self.clock_engine.solve(spec.target_sysclk_mhz)

        # Build pin-AF summary for the LLM
        af_summary = self._build_af_summary()

        system = SYSTEM_PROMPT.format(
            mcu_name=self.mcu.name,
            max_sysclk=self.mcu.max_sysclk_mhz,
            max_apb1=self.mcu.max_apb1_mhz,
            max_apb2=self.mcu.max_apb2_mhz,
            pin_af_summary=af_summary,
            apb1_timer_mhz=clock.apb1_timer_mhz,
            apb2_timer_mhz=clock.apb2_timer_mhz,
        )

        user_msg = f"RequirementSpec:\n{spec.model_dump_json(indent=2)}"

        data = self.client.reason_json(system, user_msg)

        # Inject the deterministically-solved clock config
        data["clock"] = clock.model_dump()
        data["mcu"] = self.mcu.name
        if "project_name" not in data:
            data["project_name"] = spec.project_name

        blueprint = ProjectBlueprint(**data)
        log.info("Blueprint designed: %d gpios, %d uarts, %d timers, %d adcs",
                 len(blueprint.gpios), len(blueprint.uarts),
                 len(blueprint.timers), len(blueprint.adcs))
        return blueprint

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
