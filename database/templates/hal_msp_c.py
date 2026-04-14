"""stm32f4xx_hal_msp.c template generator — HAL MSP (MCU Support Package) init callbacks."""

from __future__ import annotations


def generate_hal_msp_c(
    uart_msp_blocks: list[str],
    spi_msp_blocks: list[str],
    i2c_msp_blocks: list[str],
    tim_msp_blocks: list[str],
    adc_msp_blocks: list[str],
) -> str:
    """Generate the HAL MSP init file.

    Each block is a conditional body (if instance == X) to be placed
    inside the appropriate HAL_xxx_MspInit callback.
    """
    # Build HAL_UART_MspInit
    uart_body = "\n".join(uart_msp_blocks) if uart_msp_blocks else "  /* No UART configured */"
    spi_body = "\n".join(spi_msp_blocks) if spi_msp_blocks else ""
    i2c_body = "\n".join(i2c_msp_blocks) if i2c_msp_blocks else ""
    tim_body = "\n".join(tim_msp_blocks) if tim_msp_blocks else ""
    adc_body = "\n".join(adc_msp_blocks) if adc_msp_blocks else ""

    sections = []
    sections.append(f"""\
#include "main.h"

void HAL_MspInit(void)
{{
  __HAL_RCC_SYSCFG_CLK_ENABLE();
  __HAL_RCC_PWR_CLK_ENABLE();
}}""")

    if uart_msp_blocks:
        sections.append(f"""\
void HAL_UART_MspInit(UART_HandleTypeDef *uartHandle)
{{
  GPIO_InitTypeDef GPIO_InitStruct = {{0}};
{uart_body}
}}""")

    if spi_msp_blocks:
        sections.append(f"""\
void HAL_SPI_MspInit(SPI_HandleTypeDef *spiHandle)
{{
  GPIO_InitTypeDef GPIO_InitStruct = {{0}};
{spi_body}
}}""")

    if i2c_msp_blocks:
        sections.append(f"""\
void HAL_I2C_MspInit(I2C_HandleTypeDef *i2cHandle)
{{
  GPIO_InitTypeDef GPIO_InitStruct = {{0}};
{i2c_body}
}}""")

    if tim_msp_blocks:
        sections.append(f"""\
void HAL_TIM_Base_MspInit(TIM_HandleTypeDef *htimHandle)
{{
  GPIO_InitTypeDef GPIO_InitStruct = {{0}};
{tim_body}
}}""")

    if adc_msp_blocks:
        sections.append(f"""\
void HAL_ADC_MspInit(ADC_HandleTypeDef *adcHandle)
{{
  GPIO_InitTypeDef GPIO_InitStruct = {{0}};
{adc_body}
}}""")

    return "\n\n".join(sections) + "\n"
