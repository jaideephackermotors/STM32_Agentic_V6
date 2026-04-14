"""ADC cookbook recipe with DMA support."""

from __future__ import annotations
from database.peripheral_cookbook.base import CookbookRecipe, PeripheralCode
from schemas.peripheral_config import ADCConfig
from schemas.mcu_profile import MCUProfile
from core.dma_engine import DMAEngine
from database.mcu.stm32f446re import ADC_CHANNEL_PINS


class ADCCookbook(CookbookRecipe):
    """Generates ADC peripheral init code with optional DMA."""

    def __init__(self, mcu: MCUProfile, dma_engine: DMAEngine = None):
        super().__init__(mcu)
        self.dma_engine = dma_engine or DMAEngine(mcu)

    def generate(self, config: ADCConfig) -> PeripheralCode:
        inst = config.instance
        handle = f"hadc{inst[-1]}"
        periph = self._find_peripheral(inst)

        res_map = {12: "ADC_RESOLUTION_12B", 10: "ADC_RESOLUTION_10B",
                   8: "ADC_RESOLUTION_8B", 6: "ADC_RESOLUTION_6B"}
        resolution = res_map[config.resolution]
        scan = "ENABLE" if config.scan or len(config.channels) > 1 else "DISABLE"
        cont = "ENABLE" if config.continuous else "DISABLE"
        nbr = len(config.channels) or 1

        # Channel config blocks
        ch_blocks = []
        for ch in config.channels:
            samp_map = {3: "ADC_SAMPLETIME_3CYCLES", 15: "ADC_SAMPLETIME_15CYCLES",
                        28: "ADC_SAMPLETIME_28CYCLES", 56: "ADC_SAMPLETIME_56CYCLES",
                        84: "ADC_SAMPLETIME_84CYCLES", 112: "ADC_SAMPLETIME_112CYCLES",
                        144: "ADC_SAMPLETIME_144CYCLES", 480: "ADC_SAMPLETIME_480CYCLES"}
            samp = samp_map.get(ch.sampling_time, "ADC_SAMPLETIME_84CYCLES")
            ch_blocks.append(
                f"  sConfig.Channel = ADC_CHANNEL_{ch.channel};\n"
                f"  sConfig.Rank = {ch.rank}U;\n"
                f"  sConfig.SamplingTime = {samp};\n"
                f"  if (HAL_ADC_ConfigChannel(&{handle}, &sConfig) != HAL_OK)\n"
                f"  {{\n"
                f"    Error_Handler();\n"
                f"  }}"
            )

        ch_code = "\n\n".join(ch_blocks)

        init_fn = f"""\
static void MX_{inst}_Init(void)
{{
  ADC_ChannelConfTypeDef sConfig = {{0}};

  {handle}.Instance = {inst};
  {handle}.Init.ClockPrescaler = ADC_CLOCK_SYNC_PCLK_DIV4;
  {handle}.Init.Resolution = {resolution};
  {handle}.Init.ScanConvMode = {scan};
  {handle}.Init.ContinuousConvMode = {cont};
  {handle}.Init.DiscontinuousConvMode = DISABLE;
  {handle}.Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_NONE;
  {handle}.Init.ExternalTrigConv = ADC_SOFTWARE_START;
  {handle}.Init.DataAlign = ADC_DATAALIGN_RIGHT;
  {handle}.Init.NbrOfConversion = {nbr}U;
  {handle}.Init.DMAContinuousRequests = {"ENABLE" if config.dma else "DISABLE"};
  {handle}.Init.EOCSelection = ADC_EOC_SINGLE_CONV;
  if (HAL_ADC_Init(&{handle}) != HAL_OK)
  {{
    Error_Handler();
  }}

{ch_code}
}}"""

        # MSP — clock enable + GPIO analog pins + DMA
        msp_lines = [
            f"  if (adcHandle->Instance == {inst})",
            "  {",
            f"    {periph.rcc_macro}();",
        ]
        ports = set()
        for ch in config.channels:
            if ch.pin and ch.pin != "internal":
                ports.add(ch.pin[1])
        for port in sorted(ports):
            from database.mcu.stm32f446re import GPIO_PORT_RCC
            msp_lines.append(f"    {GPIO_PORT_RCC[port]}();")

        if any(ch.pin and ch.pin != "internal" for ch in config.channels):
            msp_lines.append("")
            msp_lines.append("    GPIO_InitTypeDef GPIO_InitStruct = {0};")
            for ch in config.channels:
                if ch.pin and ch.pin != "internal":
                    msp_lines.append(f"    /* ADC CH{ch.channel} — {ch.pin} */")
                    msp_lines.append(f"    GPIO_InitStruct.Pin = {self._pin_number_macro(ch.pin)};")
                    msp_lines.append("    GPIO_InitStruct.Mode = GPIO_MODE_ANALOG;")
                    msp_lines.append("    GPIO_InitStruct.Pull = GPIO_NOPULL;")
                    msp_lines.append(f"    HAL_GPIO_Init({self._pin_port_macro(ch.pin)}, &GPIO_InitStruct);")

        # DMA
        extra_handles = []
        extra_irq_handlers = {}
        extra_hal_sources = []
        extra_hal_modules = []

        if config.dma:
            mapping = self.dma_engine.lookup(inst)  # e.g. "ADC1"
            if mapping:
                dma_handle = f"hdma_{inst.lower()}"
                dma_info = self.dma_engine.generate_msp_dma_init(
                    mapping, handle, dma_handle, "periph_to_memory",
                    "halfword"  # ADC data is 16-bit
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

        hal_sources = list(set(["stm32f4xx_hal_adc.c", "stm32f4xx_hal_adc_ex.c"] + extra_hal_sources))
        hal_modules = list(set(["HAL_ADC_MODULE_ENABLED"] + extra_hal_modules))
        handles = [f"ADC_HandleTypeDef {handle};"] + extra_handles

        return PeripheralCode(
            peripheral_type="adc",
            init_function=init_fn,
            init_prototype=f"static void MX_{inst}_Init(void);",
            msp_init="\n".join(msp_lines),
            irq_handlers=extra_irq_handlers,
            hal_sources=hal_sources,
            hal_modules=hal_modules,
            handle_declarations=handles,
        )
