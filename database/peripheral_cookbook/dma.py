"""DMA cookbook recipe."""

from __future__ import annotations
from database.peripheral_cookbook.base import CookbookRecipe, PeripheralCode
from schemas.peripheral_config import DMAConfig


class DMACookbook(CookbookRecipe):
    """Generates DMA stream init code."""

    def generate(self, config: DMAConfig) -> PeripheralCode:
        handle = f"hdma{config.dma}_stream{config.stream}"

        dir_map = {
            "periph_to_memory": "DMA_PERIPH_TO_MEMORY",
            "memory_to_periph": "DMA_MEMORY_TO_PERIPH",
            "memory_to_memory": "DMA_MEMORY_TO_MEMORY",
        }
        size_map = {"byte": "DMA_PDATAALIGN_BYTE", "halfword": "DMA_PDATAALIGN_HALFWORD",
                     "word": "DMA_PDATAALIGN_WORD"}
        msize_map = {"byte": "DMA_MDATAALIGN_BYTE", "halfword": "DMA_MDATAALIGN_HALFWORD",
                      "word": "DMA_MDATAALIGN_WORD"}
        pri_map = {"low": "DMA_PRIORITY_LOW", "medium": "DMA_PRIORITY_MEDIUM",
                   "high": "DMA_PRIORITY_HIGH", "very_high": "DMA_PRIORITY_VERY_HIGH"}

        direction = dir_map[config.direction]
        psize = size_map[config.periph_data_size]
        msize = msize_map[config.mem_data_size]
        circ = "DMA_CIRCULAR" if config.circular else "DMA_NORMAL"
        priority = pri_map[config.priority]

        init_code = f"""\
  /* DMA{config.dma} Stream{config.stream} Channel{config.channel} */
  {handle}.Instance = DMA{config.dma}_Stream{config.stream};
  {handle}.Init.Channel = DMA_CHANNEL_{config.channel};
  {handle}.Init.Direction = {direction};
  {handle}.Init.PeriphInc = DMA_PINC_DISABLE;
  {handle}.Init.MemInc = DMA_MINC_ENABLE;
  {handle}.Init.PeriphDataAlignment = {psize};
  {handle}.Init.MemDataAlignment = {msize};
  {handle}.Init.Mode = {circ};
  {handle}.Init.Priority = {priority};
  {handle}.Init.FIFOMode = DMA_FIFOMODE_DISABLE;
  if (HAL_DMA_Init(&{handle}) != HAL_OK)
  {{
    Error_Handler();
  }}"""

        rcc = f"__HAL_RCC_DMA{config.dma}_CLK_ENABLE"

        return PeripheralCode(
            peripheral_type="dma",
            init_function=init_code,
            msp_init=f"    {rcc}();",
            hal_sources=["stm32f4xx_hal_dma.c", "stm32f4xx_hal_dma_ex.c"],
            hal_modules=["HAL_DMA_MODULE_ENABLED"],
            handle_declarations=[f"DMA_HandleTypeDef {handle};"],
        )
