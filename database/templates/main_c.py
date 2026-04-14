"""main.c template generator."""

from __future__ import annotations


def generate_main_c(
    includes: list[str],
    handle_declarations: list[str],
    init_prototypes: list[str],
    init_calls: list[str],
    init_functions: list[str],
    clock_config_fn: str,
) -> str:
    """Generate a complete main.c file.

    Args:
        includes: Extra #include lines (beyond standard HAL includes).
        handle_declarations: Peripheral handle variable declarations.
        init_prototypes: Forward declarations of MX_*_Init functions.
        init_calls: Function call statements for main() init section.
        init_functions: Full function bodies for MX_*_Init and SystemClock_Config.
        clock_config_fn: SystemClock_Config() function body.
    """
    includes_block = "\n".join(includes) if includes else ""
    handles_block = "\n".join(handle_declarations) if handle_declarations else ""
    protos_block = "\n".join(init_prototypes) if init_prototypes else ""
    calls_block = "\n".join(f"  {c}" for c in init_calls) if init_calls else ""
    fns_block = "\n\n".join(init_functions) if init_functions else ""

    return f"""\
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include <string.h>
#include <stdio.h>
{includes_block}

/* Private variables ---------------------------------------------------------*/
{handles_block}

/* USER CODE BEGIN PV */

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
{protos_block}
void Error_Handler(void);

/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{{
  /* MCU Configuration--------------------------------------------------------*/
  HAL_Init();

  /* Configure the system clock */
  SystemClock_Config();

  /* Initialize all configured peripherals */
{calls_block}

  /* USER CODE BEGIN 2 */

  /* USER CODE END 2 */

  /* Infinite loop */
  while (1)
  {{
    /* USER CODE BEGIN 3 */

    /* USER CODE END 3 */
  }}
}}

{clock_config_fn}

{fns_block}

/* USER CODE BEGIN 4 */

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{{
  /* USER CODE BEGIN Error_Handler_Debug */
  __disable_irq();
  while (1)
  {{
  }}
  /* USER CODE END Error_Handler_Debug */
}}

#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line)
{{
  /* USER CODE BEGIN 6 */
  (void)file;
  (void)line;
  /* USER CODE END 6 */
}}
#endif /* USE_FULL_ASSERT */
"""
