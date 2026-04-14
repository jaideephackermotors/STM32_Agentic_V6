"""SPI cookbook recipe."""

from __future__ import annotations
from database.peripheral_cookbook.base import CookbookRecipe, PeripheralCode
from schemas.peripheral_config import SPIConfig
from schemas.mcu_profile import MCUProfile
from core.gpio_engine import GPIOEngine
from core.dma_engine import DMAEngine


class SPICookbook(CookbookRecipe):
    """Generates SPI peripheral init code with optional DMA."""

    def __init__(self, mcu: MCUProfile, dma_engine: DMAEngine = None):
        super().__init__(mcu)
        self.gpio = GPIOEngine(mcu)
        self.dma_engine = dma_engine or DMAEngine(mcu)

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

        extra_handles = []
        extra_irq_handlers = {}
        extra_hal_sources = []
        extra_hal_modules = []

        # DMA TX
        if config.dma_tx:
            mapping = self.dma_engine.lookup(f"{inst}_TX")
            if mapping:
                dma_handle = f"hdma_{inst.lower()}_tx"
                dma_info = self.dma_engine.generate_msp_dma_init(
                    mapping, handle, dma_handle, "memory_to_periph",
                    "byte" if config.data_size == 8 else "halfword"
                )
                msp_lines.append("")
                msp_lines.append(dma_info["msp_code"])
                extra_handles.append(dma_info["handle_decl"])
                extra_irq_handlers[dma_info["irq_handler_name"]] = dma_info["irq_handler_code"]
                extra_hal_sources.extend(dma_info["hal_sources"])
                extra_hal_modules.extend(dma_info["hal_modules"])

        # DMA RX
        if config.dma_rx:
            mapping = self.dma_engine.lookup(f"{inst}_RX")
            if mapping:
                dma_handle = f"hdma_{inst.lower()}_rx"
                dma_info = self.dma_engine.generate_msp_dma_init(
                    mapping, handle, dma_handle, "periph_to_memory",
                    "byte" if config.data_size == 8 else "halfword"
                )
                msp_lines.append("")
                msp_lines.append(dma_info["msp_code"])
                extra_handles.append(dma_info["handle_decl"])
                extra_irq_handlers[dma_info["irq_handler_name"]] = dma_info["irq_handler_code"]
                extra_hal_sources.extend(dma_info["hal_sources"])
                extra_hal_modules.extend(dma_info["hal_modules"])

        if config.interrupt:
            for irq in periph.irq_names:
                msp_lines.append(f"    HAL_NVIC_SetPriority({irq}, 5, 0);")
                msp_lines.append(f"    HAL_NVIC_EnableIRQ({irq});")

        msp_lines.append("  }")

        hal_sources = list(set(["stm32f4xx_hal_spi.c"] + extra_hal_sources))
        hal_modules = list(set(["HAL_SPI_MODULE_ENABLED"] + extra_hal_modules))
        handles = [f"SPI_HandleTypeDef {handle};"] + extra_handles

        return PeripheralCode(
            peripheral_type="spi",
            init_function=init_fn,
            init_prototype=f"static void MX_{inst}_Init(void);",
            msp_init="\n".join(msp_lines),
            irq_handlers=extra_irq_handlers,
            hal_sources=hal_sources,
            hal_modules=hal_modules,
            handle_declarations=handles,
        )
