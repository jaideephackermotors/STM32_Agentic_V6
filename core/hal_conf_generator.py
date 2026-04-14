"""stm32f4xx_hal_conf.h generator — enables only the HAL modules needed."""

from __future__ import annotations


# All possible HAL modules for STM32F4
ALL_HAL_MODULES = [
    "HAL_MODULE_ENABLED",
    "HAL_ADC_MODULE_ENABLED",
    "HAL_CAN_MODULE_ENABLED",
    "HAL_CRC_MODULE_ENABLED",
    "HAL_DAC_MODULE_ENABLED",
    "HAL_DMA_MODULE_ENABLED",
    "HAL_FLASH_MODULE_ENABLED",
    "HAL_GPIO_MODULE_ENABLED",
    "HAL_I2C_MODULE_ENABLED",
    "HAL_IWDG_MODULE_ENABLED",
    "HAL_PWR_MODULE_ENABLED",
    "HAL_RCC_MODULE_ENABLED",
    "HAL_RTC_MODULE_ENABLED",
    "HAL_SPI_MODULE_ENABLED",
    "HAL_TIM_MODULE_ENABLED",
    "HAL_UART_MODULE_ENABLED",
    "HAL_USART_MODULE_ENABLED",
    "HAL_WWDG_MODULE_ENABLED",
    "HAL_CORTEX_MODULE_ENABLED",
]

# Always-on modules (needed for basic operation)
ALWAYS_ENABLED = {
    "HAL_MODULE_ENABLED",
    "HAL_FLASH_MODULE_ENABLED",
    "HAL_GPIO_MODULE_ENABLED",
    "HAL_PWR_MODULE_ENABLED",
    "HAL_RCC_MODULE_ENABLED",
    "HAL_CORTEX_MODULE_ENABLED",
    "HAL_DMA_MODULE_ENABLED",
}


class HALConfGenerator:
    """Generates stm32f4xx_hal_conf.h with only needed modules enabled."""

    def generate(self, enabled_modules: list[str]) -> str:
        """Generate hal_conf.h content.

        Args:
            enabled_modules: List of HAL_xxx_MODULE_ENABLED macros to enable.
        """
        enabled = ALWAYS_ENABLED | set(enabled_modules)

        module_defines = []
        for mod in ALL_HAL_MODULES:
            if mod in enabled:
                module_defines.append(f"#define {mod}")
            else:
                module_defines.append(f"/* #define {mod} */")

        modules_block = "\n".join(module_defines)

        return f"""\
#ifndef __STM32F4xx_HAL_CONF_H
#define __STM32F4xx_HAL_CONF_H

#ifdef __cplusplus
extern "C" {{
#endif

/* ########################## Module Selection ############################## */
{modules_block}

/* ########################## HSE/HSI Values ################################ */
#if !defined  (HSE_VALUE)
  #define HSE_VALUE    8000000U
#endif

#if !defined  (HSE_STARTUP_TIMEOUT)
  #define HSE_STARTUP_TIMEOUT    100U
#endif

#if !defined  (HSI_VALUE)
  #define HSI_VALUE    16000000U
#endif

#if !defined  (LSI_VALUE)
  #define LSI_VALUE    32000U
#endif

#if !defined  (LSE_VALUE)
  #define LSE_VALUE    32768U
#endif

#if !defined  (LSE_STARTUP_TIMEOUT)
  #define LSE_STARTUP_TIMEOUT    5000U
#endif

#if !defined  (EXTERNAL_CLOCK_VALUE)
  #define EXTERNAL_CLOCK_VALUE    12288000U
#endif

/* ########################### System Configuration ######################### */
#define  VDD_VALUE                    3300U
#define  TICK_INT_PRIORITY            0x0FU
#define  USE_RTOS                     0U
#define  PREFETCH_ENABLE              1U
#define  INSTRUCTION_CACHE_ENABLE     1U
#define  DATA_CACHE_ENABLE            1U

/* ########################## Assert Selection ############################## */
#define USE_FULL_ASSERT    1U

/* Includes ------------------------------------------------------------------*/
#ifdef HAL_RCC_MODULE_ENABLED
  #include "stm32f4xx_hal_rcc.h"
#endif

#ifdef HAL_GPIO_MODULE_ENABLED
  #include "stm32f4xx_hal_gpio.h"
#endif

#ifdef HAL_DMA_MODULE_ENABLED
  #include "stm32f4xx_hal_dma.h"
#endif

#ifdef HAL_CORTEX_MODULE_ENABLED
  #include "stm32f4xx_hal_cortex.h"
#endif

#ifdef HAL_ADC_MODULE_ENABLED
  #include "stm32f4xx_hal_adc.h"
#endif

#ifdef HAL_CAN_MODULE_ENABLED
  #include "stm32f4xx_hal_can.h"
#endif

#ifdef HAL_DAC_MODULE_ENABLED
  #include "stm32f4xx_hal_dac.h"
#endif

#ifdef HAL_FLASH_MODULE_ENABLED
  #include "stm32f4xx_hal_flash.h"
#endif

#ifdef HAL_I2C_MODULE_ENABLED
  #include "stm32f4xx_hal_i2c.h"
#endif

#ifdef HAL_IWDG_MODULE_ENABLED
  #include "stm32f4xx_hal_iwdg.h"
#endif

#ifdef HAL_PWR_MODULE_ENABLED
  #include "stm32f4xx_hal_pwr.h"
#endif

#ifdef HAL_RTC_MODULE_ENABLED
  #include "stm32f4xx_hal_rtc.h"
#endif

#ifdef HAL_SPI_MODULE_ENABLED
  #include "stm32f4xx_hal_spi.h"
#endif

#ifdef HAL_TIM_MODULE_ENABLED
  #include "stm32f4xx_hal_tim.h"
#endif

#ifdef HAL_UART_MODULE_ENABLED
  #include "stm32f4xx_hal_uart.h"
#endif

#ifdef HAL_USART_MODULE_ENABLED
  #include "stm32f4xx_hal_usart.h"
#endif

#ifdef HAL_WWDG_MODULE_ENABLED
  #include "stm32f4xx_hal_wwdg.h"
#endif

/* Exported macro ------------------------------------------------------------*/
#ifdef  USE_FULL_ASSERT
  #define assert_param(expr) ((expr) ? (void)0U : assert_failed((uint8_t *)__FILE__, __LINE__))
  void assert_failed(uint8_t* file, uint32_t line);
#else
  #define assert_param(expr) ((void)0U)
#endif

#ifdef __cplusplus
}}
#endif

#endif /* __STM32F4xx_HAL_CONF_H */
"""
