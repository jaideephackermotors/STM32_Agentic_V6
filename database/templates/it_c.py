"""stm32f4xx_it.c interrupt handler template generator."""

from __future__ import annotations


def generate_it_c(
    handle_externs: list[str],
    irq_handlers: dict[str, str],
) -> str:
    """Generate the interrupt handler source file.

    Args:
        handle_externs: extern declarations for peripheral handles.
        irq_handlers: map of handler_name → function body string.
    """
    externs_block = "\n".join(f"extern {h}" for h in handle_externs)
    handlers_block = "\n\n".join(irq_handlers.values()) if irq_handlers else ""

    return f"""\
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "stm32f4xx_it.h"

/* External variables --------------------------------------------------------*/
{externs_block}

/* USER CODE BEGIN EV */

/* USER CODE END EV */

/******************************************************************************/
/*           Cortex-M4 Processor Interruption and Exception Handlers          */
/******************************************************************************/

void NMI_Handler(void)
{{
  while (1)
  {{
  }}
}}

void HardFault_Handler(void)
{{
  while (1)
  {{
  }}
}}

void MemManage_Handler(void)
{{
  while (1)
  {{
  }}
}}

void BusFault_Handler(void)
{{
  while (1)
  {{
  }}
}}

void UsageFault_Handler(void)
{{
  while (1)
  {{
  }}
}}

void SVC_Handler(void)
{{
}}

void DebugMon_Handler(void)
{{
}}

void PendSV_Handler(void)
{{
}}

void SysTick_Handler(void)
{{
  HAL_IncTick();
}}

/******************************************************************************/
/* STM32F4xx Peripheral Interrupt Handlers                                    */
/******************************************************************************/

{handlers_block}

/* USER CODE BEGIN 1 */

/* USER CODE END 1 */
"""
