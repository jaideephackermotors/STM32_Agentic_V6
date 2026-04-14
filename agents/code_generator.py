"""Code Generator Agent — generates application logic for USER CODE regions.

Init code is generated deterministically by cookbook recipes.
This agent ONLY generates the application logic (main loop, callbacks, ISR code).
"""

from __future__ import annotations
import json
import logging

from agents.agent_base import DeepSeekClient
from schemas.blueprint import ProjectBlueprint
from schemas.requirements import RequirementSpec

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert STM32 embedded C programmer.

Your job: Generate application logic code for the USER CODE regions of an STM32 project.
All peripheral initialization is ALREADY DONE — you only write application logic.

AVAILABLE HANDLES (already declared):
{handles}

AVAILABLE HAL FUNCTIONS:
{hal_functions}

PIN DEFINES:
{pin_defines}

PROJECT CONTEXT:
{project_context}

OUTPUT FORMAT — return ONLY JSON:
{{
  "code_blocks": [
    {{
      "region": "PV",
      "file": "main.c",
      "code": "volatile uint32_t tick_count = 0U;"
    }},
    {{
      "region": "2",
      "file": "main.c",
      "code": "HAL_TIM_Base_Start_IT(&htim2);"
    }},
    {{
      "region": "3",
      "file": "main.c",
      "code": "HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_5);\\nHAL_Delay(500U);"
    }},
    {{
      "region": "4",
      "file": "main.c",
      "code": "void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)\\n{{...}}"
    }}
  ]
}}

REGIONS:
  PV = Private Variables (volatile ISR-shared vars)
  PFP = Private Function Prototypes
  0 = Before HAL_Init (rare)
  2 = After peripheral init, before main loop (start timers, etc.)
  3 = Inside while(1) main loop body
  4 = After main loop (callbacks, helper functions)
  Error_Handler_Debug = Inside Error_Handler

RULES:
1. ONLY use handles and functions from the lists above. NO OTHERS.
2. Use volatile for any variable shared between ISR and main.
3. Always check HAL return values.
4. Use U suffix on integer literals (MISRA).
5. No magic numbers — use #define or const.
6. Return ONLY the JSON, no markdown.
"""


class CodeGeneratorAgent:
    """Generates application logic using DeepSeek Reasoner."""

    def __init__(self, client: DeepSeekClient):
        self.client = client

    def generate(
        self,
        spec: RequirementSpec,
        blueprint: ProjectBlueprint,
        vocabulary: dict,
    ) -> list[dict]:
        """Generate application code blocks.

        Args:
            spec: Original requirements.
            blueprint: Project blueprint with all peripheral configs.
            vocabulary: Extracted identifiers from generated project files.

        Returns:
            List of code block dicts with region/file/code keys.
        """
        system = SYSTEM_PROMPT.format(
            handles="\n".join(f"  {h}" for h in vocabulary.get("handles", [])),
            hal_functions="\n".join(f"  {f}" for f in sorted(vocabulary.get("hal_functions", []))[:100]),
            pin_defines="\n".join(f"  {d}" for d in vocabulary.get("pin_defines", [])),
            project_context=spec.description or spec.raw_text,
        )

        user_msg = (
            f"Requirements:\n{spec.raw_text}\n\n"
            f"Blueprint summary:\n"
            f"  GPIOs: {[g.pin + '(' + g.label + ')' for g in blueprint.gpios]}\n"
            f"  UARTs: {[u.instance + '@' + str(u.baud_rate) for u in blueprint.uarts]}\n"
            f"  Timers: {[t.instance + '/' + t.mode for t in blueprint.timers]}\n"
            f"  ADCs: {[a.instance for a in blueprint.adcs]}\n"
        )

        data = self.client.reason_json(system, user_msg)
        blocks = data.get("code_blocks", [])
        log.info("Generated %d code blocks", len(blocks))
        return blocks
