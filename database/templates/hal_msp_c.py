"""stm32f4xx_hal_msp.c template generator — HAL MSP (MCU Support Package) init callbacks."""

from __future__ import annotations


def generate_hal_msp_c(
    uart_msp_blocks: list[str],
    spi_msp_blocks: list[str],
    i2c_msp_blocks: list[str],
    tim_msp_blocks: list[str],
    adc_msp_blocks: list[str],
    handle_declarations: list[str] = None,
) -> str:
    """Generate the HAL MSP init file.

    Args:
        *_msp_blocks: MSP init code blocks grouped by peripheral type.
        handle_declarations: Global handle declarations from main.c
            (emitted as extern in this file so DMA linking works).
    """
    # Build extern declarations for handles used in DMA linking
    extern_block = ""
    if handle_declarations:
        extern_lines = []
        for decl in handle_declarations:
            # "UART_HandleTypeDef huart2;" → "extern UART_HandleTypeDef huart2;"
            clean = decl.strip().rstrip(";")
            extern_lines.append(f"extern {clean};")
        extern_block = "\n".join(extern_lines) + "\n"

    sections = []
    sections.append(f"""\
#include "main.h"

{extern_block}
void HAL_MspInit(void)
{{
  __HAL_RCC_SYSCFG_CLK_ENABLE();
  __HAL_RCC_PWR_CLK_ENABLE();
}}""")

    if uart_msp_blocks:
        uart_body = "\n".join(uart_msp_blocks)
        sections.append(f"""\
void HAL_UART_MspInit(UART_HandleTypeDef *uartHandle)
{{
{uart_body}
}}""")

    if spi_msp_blocks:
        spi_body = "\n".join(spi_msp_blocks)
        sections.append(f"""\
void HAL_SPI_MspInit(SPI_HandleTypeDef *spiHandle)
{{
{spi_body}
}}""")

    if i2c_msp_blocks:
        i2c_body = "\n".join(i2c_msp_blocks)
        sections.append(f"""\
void HAL_I2C_MspInit(I2C_HandleTypeDef *i2cHandle)
{{
{i2c_body}
}}""")

    if tim_msp_blocks:
        tim_body = "\n".join(tim_msp_blocks)
        sections.append(f"""\
void HAL_TIM_Base_MspInit(TIM_HandleTypeDef *htimHandle)
{{
{tim_body}
}}""")

    if adc_msp_blocks:
        adc_body = "\n".join(adc_msp_blocks)
        sections.append(f"""\
void HAL_ADC_MspInit(ADC_HandleTypeDef *adcHandle)
{{
{adc_body}
}}""")

    return "\n\n".join(sections) + "\n"
