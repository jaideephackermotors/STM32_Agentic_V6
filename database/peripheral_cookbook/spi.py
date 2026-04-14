"""SPI cookbook recipe."""

from __future__ import annotations
from database.peripheral_cookbook.base import CookbookRecipe, PeripheralCode
from schemas.peripheral_config import SPIConfig
from schemas.mcu_profile import MCUProfile
from core.gpio_engine import GPIOEngine


class SPICookbook(CookbookRecipe):
    """Generates SPI peripheral init code."""

    def __init__(self, mcu: MCUProfile):
        super().__init__(mcu)
        self.gpio = GPIOEngine(mcu)

    def generate(self, config: SPIConfig) -> PeripheralCode:
        inst = config.instance
        handle = f"hspi{inst[-1]}"
        periph = self._find_peripheral(inst)

        mode = "SPI_MODE_MASTER" if config.mode == "master" else "SPI_MODE_SLAVE"
        cpol = "SPI_POLARITY_LOW" if config.cpol == 0 else "SPI_POLARITY_HIGH"
        cpha = "SPI_PHASE_1EDGE" if config.cpha == 0 else "SPI_PHASE_2EDGE"
        dsize = "SPI_DATASIZE_8BIT" if config.data_size == 8 else "SPI_DATASIZE_16BIT"
        fbit = "SPI_FIRSTBIT_MSB" if config.first_bit == "msb" else "SPI_FIRSTBIT_LSB"

        prescaler_map = {
            2: "SPI_BAUDRATEPRESCALER_2", 4: "SPI_BAUDRATEPRESCALER_4",
            8: "SPI_BAUDRATEPRESCALER_8", 16: "SPI_BAUDRATEPRESCALER_16",
            32: "SPI_BAUDRATEPRESCALER_32", 64: "SPI_BAUDRATEPRESCALER_64",
            128: "SPI_BAUDRATEPRESCALER_128", 256: "SPI_BAUDRATEPRESCALER_256",
        }
        baud = prescaler_map.get(config.baud_prescaler, "SPI_BAUDRATEPRESCALER_16")
        nss = "SPI_NSS_SOFT" if config.nss_pin is None else "SPI_NSS_HARD_OUTPUT"

        init_fn = f"""\
static void MX_{inst}_Init(void)
{{
  {handle}.Instance = {inst};
  {handle}.Init.Mode = {mode};
  {handle}.Init.Direction = SPI_DIRECTION_2LINES;
  {handle}.Init.DataSize = {dsize};
  {handle}.Init.CLKPolarity = {cpol};
  {handle}.Init.CLKPhase = {cpha};
  {handle}.Init.NSS = {nss};
  {handle}.Init.BaudRatePrescaler = {baud};
  {handle}.Init.FirstBit = {fbit};
  {handle}.Init.TIMode = SPI_TIMODE_DISABLE;
  {handle}.Init.CRCCalculation = SPI_CRCCALCULATION_DISABLE;
  {handle}.Init.CRCPolynomial = 10U;
  if (HAL_SPI_Init(&{handle}) != HAL_OK)
  {{
    Error_Handler();
  }}
}}"""

        # MSP
        msp_lines = [
            f"  if (spiHandle->Instance == {inst})",
            "  {",
            f"    {periph.rcc_macro}();",
        ]
        pins = [
            (config.sck_pin, f"{inst}_SCK"),
            (config.mosi_pin, f"{inst}_MOSI"),
            (config.miso_pin, f"{inst}_MISO"),
        ]
        if config.nss_pin:
            pins.append((config.nss_pin, f"{inst}_NSS"))

        ports = set(p[0][1] for p in pins)
        for port in sorted(ports):
            from database.mcu.stm32f446re import GPIO_PORT_RCC
            msp_lines.append(f"    {GPIO_PORT_RCC[port]}();")

        msp_lines.append("")
        msp_lines.append("    GPIO_InitTypeDef GPIO_InitStruct = {0};")

        for pin, signal in pins:
            af = self.gpio.lookup_af(pin, signal)
            msp_lines.append(f"    /* {signal} — {pin} */")
            msp_lines.append(f"    GPIO_InitStruct.Pin = {self._pin_number_macro(pin)};")
            msp_lines.append("    GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;")
            msp_lines.append("    GPIO_InitStruct.Pull = GPIO_NOPULL;")
            msp_lines.append("    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;")
            msp_lines.append(f"    GPIO_InitStruct.Alternate = GPIO_AF{af}_{inst};")
            msp_lines.append(f"    HAL_GPIO_Init({self._pin_port_macro(pin)}, &GPIO_InitStruct);")

        if config.interrupt:
            for irq in periph.irq_names:
                msp_lines.append(f"    HAL_NVIC_SetPriority({irq}, 5, 0);")
                msp_lines.append(f"    HAL_NVIC_EnableIRQ({irq});")

        msp_lines.append("  }")

        return PeripheralCode(
            init_function=init_fn,
            init_prototype=f"static void MX_{inst}_Init(void);",
            msp_init="\n".join(msp_lines),
            hal_sources=["stm32f4xx_hal_spi.c"],
            hal_modules=["HAL_SPI_MODULE_ENABLED"],
            handle_declarations=[f"SPI_HandleTypeDef {handle};"],
        )
