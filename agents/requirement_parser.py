"""Requirement Parser Agent — converts natural language to RequirementSpec JSON."""

from __future__ import annotations
import json
import logging

from agents.agent_base import DeepSeekClient
from schemas.requirements import RequirementSpec
from schemas.mcu_profile import MCUProfile

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert STM32 embedded systems requirements analyst.

Your job: Parse natural language requirements into a structured JSON specification.

TARGET MCU: {mcu_name}
AVAILABLE PERIPHERALS: {peripherals}
AVAILABLE GPIO PORTS: {gpio_ports}

OUTPUT FORMAT — you MUST return ONLY valid JSON matching this schema:
{{
  "project_name": "string — short snake_case name",
  "mcu": "{mcu_name}",
  "target_sysclk_mhz": 180,
  "peripherals": [
    {{
      "type": "uart|spi|i2c|timer|adc|gpio|dma",
      "instance": "USART2|TIM5|ADC1|PA5|etc",
      "purpose": "human-readable description",
      "parameters": {{"baud_rate": 115200}},
      "pins": ["PA2", "PA3"],
      "interrupt": false,
      "dma": false
    }}
  ],
  "rtos": false,
  "description": "one-line project summary"
}}

RULES:
1. Only use peripheral instances that EXIST on this MCU.
2. Only assign pins that have valid AF mappings for the peripheral.
3. If the user doesn't specify a pin, pick the most common default.
4. If frequency/baud/resolution is not specified, ASK — do not guess.
5. For timers: calculate prescaler and period if the user specifies a frequency.
6. Return ONLY the JSON. No markdown, no explanation.
"""


class RequirementParserAgent:
    """Parses natural language requirements into structured RequirementSpec."""

    def __init__(self, client: DeepSeekClient, mcu: MCUProfile):
        self.client = client
        self.mcu = mcu

    def parse(self, requirements_text: str) -> RequirementSpec:
        """Parse requirements text into RequirementSpec.

        Raises ValueError if parsing fails after retries.
        """
        system = SYSTEM_PROMPT.format(
            mcu_name=self.mcu.name,
            peripherals=", ".join(p.name for p in self.mcu.peripherals),
            gpio_ports=", ".join(self.mcu.gpio_ports),
        )

        user_msg = f"Requirements:\n{requirements_text}"

        data = self.client.reason_json(system, user_msg)

        # Add raw text
        data["raw_text"] = requirements_text
        if "mcu" not in data:
            data["mcu"] = self.mcu.name

        spec = RequirementSpec(**data)
        log.info("Parsed %d peripheral requirements for project '%s'",
                 len(spec.peripherals), spec.project_name)
        return spec
