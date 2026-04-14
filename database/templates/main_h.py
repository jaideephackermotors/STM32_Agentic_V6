"""main.h template generator."""

from __future__ import annotations


def generate_main_h(
    pin_defines: list[tuple[str, str, int]] | None = None,
) -> str:
    """Generate main.h header file.

    Args:
        pin_defines: List of (label, port_letter, pin_number) for GPIO defines.
                     e.g. [("LED", "A", 5)] → #define LED_Pin GPIO_PIN_5
    """
    defines_block = ""
    if pin_defines:
        for label, port, pin_num in pin_defines:
            defines_block += f"#define {label}_Pin GPIO_PIN_{pin_num}\n"
            defines_block += f"#define {label}_GPIO_Port GPIO{port}\n"

    return f"""\
/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {{
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32f4xx_hal.h"

/* Exported functions prototypes ---------------------------------------------*/
void Error_Handler(void);

/* USER CODE BEGIN EFP */

/* USER CODE END EFP */

/* Private defines -----------------------------------------------------------*/
{defines_block}
/* USER CODE BEGIN Private defines */

/* USER CODE END Private defines */

#ifdef __cplusplus
}}
#endif

#endif /* __MAIN_H */
"""
