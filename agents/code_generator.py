"""Code Generator Agent — generates application logic for USER CODE regions.

Init code is generated deterministically by cookbook recipes.
This agent ONLY generates the application logic (main loop, callbacks, ISR code).
"""

from __future__ import annotations
import json
import logging

from agents.agent_base import DeepSeekClient
from agents.failure_log import FailureLog
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
      "code": "    HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_5);\\n    HAL_Delay(500U);"
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

ALREADY DEFINED (do NOT redefine these):
  - SystemClock_Config(), Error_Handler(), assert_failed() — already in main.c
  - All MX_*_Init() functions — already generated
  - All peripheral handles (e.g. htim2, huart2) — already declared globally
  - main() function — already exists
  You ONLY provide code that goes INSIDE the USER CODE regions.
  For region 4: only write HAL callbacks (e.g. HAL_TIM_PeriodElapsedCallback).
  Do NOT write function prototypes for callbacks — they are declared in HAL headers.

RULES:
1. ONLY use handles and functions from the lists above. NO OTHERS.
2. Use volatile for any variable shared between ISR and main.
3. Always check HAL return values.
4. Use U suffix on integer literals (MISRA).
5. No magic numbers — use #define or const.
6. Return ONLY the JSON, no markdown.
7. Do NOT re-declare or re-define any function that already exists in the project.
8. For region 3 (while loop body): provide ONLY the loop body statements, not the while loop itself.
9. Do NOT include #include directives — all headers are already included.
"""


class CodeGeneratorAgent:
    """Generates application logic using DeepSeek Reasoner."""

    def __init__(self, client: DeepSeekClient):
        self.client = client
        self.failure_log = FailureLog("codegen")

    def generate(
        self,
        spec: RequirementSpec,
        blueprint: ProjectBlueprint,
        vocabulary: dict,
    ) -> list[dict]:
        """Generate application code blocks."""
        # Inject past compile error lessons
        failures_section = self.failure_log.get_prompt_section()

        system = SYSTEM_PROMPT.format(
            handles="\n".join(f"  {h}" for h in vocabulary.get("handles", [])),
            hal_functions="\n".join(f"  {f}" for f in sorted(vocabulary.get("hal_functions", []))[:100]),
            pin_defines="\n".join(f"  {d}" for d in vocabulary.get("pin_defines", [])),
            project_context=spec.description or spec.raw_text,
        )
        if failures_section:
            system += "\n" + failures_section

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

    def record_compile_errors(self, errors: list) -> None:
        """Record compile errors from build stage for future prompt enrichment."""
        for err in errors:
            self.failure_log.record_compile_error(
                file=getattr(err, 'file', str(err)),
                line=getattr(err, 'line', 0),
                message=getattr(err, 'message', str(err)),
            )
