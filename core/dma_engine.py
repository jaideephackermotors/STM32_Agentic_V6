"""DMA engine — resolves DMA stream/channel assignments and generates init code.

Given a peripheral request (e.g. "USART2_TX"), looks up the correct
DMA controller, stream, and channel from the MCU profile's DMA mapping table.
"""

from __future__ import annotations
import logging
from schemas.mcu_profile import MCUProfile, DMAMapping

log = logging.getLogger(__name__)

# DMA stream IRQ names for STM32F4
DMA_IRQ_TABLE = {
    (1, 0): "DMA1_Stream0_IRQn",
    (1, 1): "DMA1_Stream1_IRQn",
    (1, 2): "DMA1_Stream2_IRQn",
    (1, 3): "DMA1_Stream3_IRQn",
    (1, 4): "DMA1_Stream4_IRQn",
    (1, 5): "DMA1_Stream5_IRQn",
    (1, 6): "DMA1_Stream6_IRQn",
    (1, 7): "DMA1_Stream7_IRQn",
    (2, 0): "DMA2_Stream0_IRQn",
    (2, 1): "DMA2_Stream1_IRQn",
    (2, 2): "DMA2_Stream2_IRQn",
    (2, 3): "DMA2_Stream3_IRQn",
    (2, 4): "DMA2_Stream4_IRQn",
    (2, 5): "DMA2_Stream5_IRQn",
    (2, 6): "DMA2_Stream6_IRQn",
    (2, 7): "DMA2_Stream7_IRQn",
}

# DMA stream IRQ handler names
DMA_HANDLER_TABLE = {
    (1, 0): "DMA1_Stream0_IRQHandler",
    (1, 1): "DMA1_Stream1_IRQHandler",
    (1, 2): "DMA1_Stream2_IRQHandler",
    (1, 3): "DMA1_Stream3_IRQHandler",
    (1, 4): "DMA1_Stream4_IRQHandler",
    (1, 5): "DMA1_Stream5_IRQHandler",
    (1, 6): "DMA1_Stream6_IRQHandler",
    (1, 7): "DMA1_Stream7_IRQHandler",
    (2, 0): "DMA2_Stream0_IRQHandler",
    (2, 1): "DMA2_Stream1_IRQHandler",
    (2, 2): "DMA2_Stream2_IRQHandler",
    (2, 3): "DMA2_Stream3_IRQHandler",
    (2, 4): "DMA2_Stream4_IRQHandler",
    (2, 5): "DMA2_Stream5_IRQHandler",
    (2, 6): "DMA2_Stream6_IRQHandler",
    (2, 7): "DMA2_Stream7_IRQHandler",
}


class DMAEngine:
    """Resolves DMA assignments and generates DMA init code for peripheral MSP."""

    def __init__(self, mcu: MCUProfile):
        self.mcu = mcu
        self._used_streams: set[tuple[int, int]] = set()  # Track (dma, stream) allocations

    def lookup(self, periph_request: str) -> DMAMapping | None:
        """Find DMA mapping for a peripheral request (e.g. 'USART2_TX').

        Returns the first available mapping that isn't already allocated.
        """
        for m in self.mcu.dma_mappings:
            if m.peripheral == periph_request:
                key = (m.dma, m.stream)
                if key not in self._used_streams:
                    self._used_streams.add(key)
                    log.info("DMA assigned: %s → DMA%d Stream%d Ch%d",
                             periph_request, m.dma, m.stream, m.channel)
                    return m
        log.warning("No DMA mapping found for %s", periph_request)
        return None

    def generate_msp_dma_init(
        self,
        mapping: DMAMapping,
        periph_handle: str,
        dma_handle_name: str,
        direction: str,
        data_size: str = "byte",
    ) -> dict:
        """Generate DMA init code for a peripheral's MSP init.

        Args:
            mapping: DMA mapping from lookup().
            periph_handle: Parent peripheral handle name (e.g. "huart2").
            dma_handle_name: DMA handle variable name (e.g. "hdma_usart2_tx").
            direction: "periph_to_memory" or "memory_to_periph".
            data_size: "byte", "halfword", or "word".

        Returns:
            dict with keys: msp_code, handle_decl, irq_handler, irq_name, hal_sources
        """
        dir_macro = {
            "periph_to_memory": "DMA_PERIPH_TO_MEMORY",
            "memory_to_periph": "DMA_MEMORY_TO_PERIPH",
        }[direction]

        size_macro = {
            "byte": ("DMA_PDATAALIGN_BYTE", "DMA_MDATAALIGN_BYTE"),
            "halfword": ("DMA_PDATAALIGN_HALFWORD", "DMA_MDATAALIGN_HALFWORD"),
            "word": ("DMA_PDATAALIGN_WORD", "DMA_MDATAALIGN_WORD"),
        }[data_size]

        irq_name = DMA_IRQ_TABLE[(mapping.dma, mapping.stream)]
        handler_name = DMA_HANDLER_TABLE[(mapping.dma, mapping.stream)]

        msp_code = f"""\
    /* DMA{mapping.dma} Stream{mapping.stream} — {mapping.peripheral} */
    __HAL_RCC_DMA{mapping.dma}_CLK_ENABLE();
    {dma_handle_name}.Instance = DMA{mapping.dma}_Stream{mapping.stream};
    {dma_handle_name}.Init.Channel = DMA_CHANNEL_{mapping.channel};
    {dma_handle_name}.Init.Direction = {dir_macro};
    {dma_handle_name}.Init.PeriphInc = DMA_PINC_DISABLE;
    {dma_handle_name}.Init.MemInc = DMA_MINC_ENABLE;
    {dma_handle_name}.Init.PeriphDataAlignment = {size_macro[0]};
    {dma_handle_name}.Init.MemDataAlignment = {size_macro[1]};
    {dma_handle_name}.Init.Mode = DMA_NORMAL;
    {dma_handle_name}.Init.Priority = DMA_PRIORITY_LOW;
    {dma_handle_name}.Init.FIFOMode = DMA_FIFOMODE_DISABLE;
    if (HAL_DMA_Init(&{dma_handle_name}) != HAL_OK)
    {{
      Error_Handler();
    }}
    __HAL_LINKDMA({periph_handle}, {self._linkdma_field(mapping.peripheral)}, {dma_handle_name});
    HAL_NVIC_SetPriority({irq_name}, 5, 0);
    HAL_NVIC_EnableIRQ({irq_name});"""

        irq_handler_code = (
            f"void {handler_name}(void)\n"
            f"{{\n"
            f"  HAL_DMA_IRQHandler(&{dma_handle_name});\n"
            f"}}\n"
        )

        return {
            "msp_code": msp_code,
            "handle_decl": f"DMA_HandleTypeDef {dma_handle_name};",
            "irq_handler_name": handler_name,
            "irq_handler_code": irq_handler_code,
            "hal_sources": ["stm32f4xx_hal_dma.c", "stm32f4xx_hal_dma_ex.c"],
            "hal_modules": ["HAL_DMA_MODULE_ENABLED"],
        }

    @staticmethod
    def _linkdma_field(periph_request: str) -> str:
        """Map peripheral request to __HAL_LINKDMA field name.

        USART2_TX → hdmatx
        USART2_RX → hdmarx
        ADC1 → DMA_Handle
        SPI1_TX → hdmatx
        SPI1_RX → hdmarx
        """
        req = periph_request.upper()
        if req.endswith("_TX"):
            return "hdmatx"
        elif req.endswith("_RX"):
            return "hdmarx"
        elif "ADC" in req:
            return "DMA_Handle"
        else:
            return "hdma"
