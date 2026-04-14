"""UART/USART cookbook recipe.

Generates MX_USARTx_UART_Init(), HAL_UART_MspInit() GPIO+clock setup,
DMA stream init (if dma_tx/dma_rx enabled), and optional IRQ handlers.
"""

from __future__ import annotations
from database.peripheral_cookbook.base import CookbookRecipe, PeripheralCode
from schemas.peripheral_config import UARTConfig
from schemas.mcu_profile import MCUProfile
from core.gpio_engine import GPIOEngine
from core.dma_engine import DMAEngine


class UARTCookbook(CookbookRecipe):
    """Deterministic UART init code generator."""

    def __init__(self, mcu: MCUProfile, dma_engine: DMAEngine = None):
        super().__init__(mcu)
        self.gpio = GPIOEngine(mcu)
        self.dma_engine = dma_engine or DMAEngine(mcu)

    def generate(self, config: UARTConfig) -> PeripheralCode:
        inst = config.instance  # e.g. "USART2"
        handle = f"huart{inst[-1]}"
        periph = self._find_peripheral(inst)

        # Word length
        wl = "UART_WORDLENGTH_8B" if config.word_length == 8 else "UART_WORDLENGTH_9B"
        # Stop bits
        sb = "UART_STOPBITS_1" if config.stop_bits == 1 else "UART_STOPBITS_2"
        # Parity
        par_map = {"none": "UART_PARITY_NONE", "even": "UART_PARITY_EVEN", "odd": "UART_PARITY_ODD"}
        par = par_map[config.parity]
        # Mode
        mode_map = {"tx_rx": "UART_MODE_TX_RX", "tx_only": "UART_MODE_TX", "rx_only": "UART_MODE_RX"}
        mode = mode_map[config.mode]

        # --- Init function ---
        init_fn = f"""\
static void MX_{inst}_UART_Init(void)
{{
  {handle}.Instance = {inst};
  {handle}.Init.BaudRate = {config.baud_rate}U;
  {handle}.Init.WordLength = {wl};
  {handle}.Init.StopBits = {sb};
  {handle}.Init.Parity = {par};
  {handle}.Init.Mode = {mode};
  {handle}.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  {handle}.Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(&{handle}) != HAL_OK)
  {{
    Error_Handler();
  }}
}}"""

        # --- MSP Init (GPIO + clock enable + DMA) ---
        tx_signal = f"{inst}_TX"
        rx_signal = f"{inst}_RX"

        msp_lines = []
        msp_lines.append(f"  if (uartHandle->Instance == {inst})")
        msp_lines.append("  {")
        msp_lines.append(f"    {periph.rcc_macro}();")

        ports_needed = set()
        if config.mode in ("tx_rx", "tx_only"):
            ports_needed.add(config.tx_pin[1])
        if config.mode in ("tx_rx", "rx_only"):
            ports_needed.add(config.rx_pin[1])
        for port in sorted(ports_needed):
            from database.mcu.stm32f446re import GPIO_PORT_RCC
            msp_lines.append(f"    {GPIO_PORT_RCC[port]}();")

        msp_lines.append("")
        msp_lines.append("    GPIO_InitTypeDef GPIO_InitStruct = {0};")

        af_periph_name = inst

        # TX pin
        if config.mode in ("tx_rx", "tx_only"):
            af = self.gpio.lookup_af(config.tx_pin, tx_signal)
            msp_lines.append(f"    /* {inst} TX — {config.tx_pin} */")
            msp_lines.append(f"    GPIO_InitStruct.Pin = {self._pin_number_macro(config.tx_pin)};")
            msp_lines.append("    GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;")
            msp_lines.append("    GPIO_InitStruct.Pull = GPIO_NOPULL;")
            msp_lines.append("    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;")
            msp_lines.append(f"    GPIO_InitStruct.Alternate = GPIO_AF{af}_{af_periph_name};")
            msp_lines.append(f"    HAL_GPIO_Init({self._pin_port_macro(config.tx_pin)}, &GPIO_InitStruct);")

        # RX pin
        if config.mode in ("tx_rx", "rx_only"):
            af = self.gpio.lookup_af(config.rx_pin, rx_signal)
            msp_lines.append(f"    /* {inst} RX — {config.rx_pin} */")
            msp_lines.append(f"    GPIO_InitStruct.Pin = {self._pin_number_macro(config.rx_pin)};")
            msp_lines.append("    GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;")
            msp_lines.append("    GPIO_InitStruct.Pull = GPIO_NOPULL;")
            msp_lines.append("    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;")
            msp_lines.append(f"    GPIO_InitStruct.Alternate = GPIO_AF{af}_{af_periph_name};")
            msp_lines.append(f"    HAL_GPIO_Init({self._pin_port_macro(config.rx_pin)}, &GPIO_InitStruct);")

        # Collect extra handle declarations, IRQ handlers, HAL sources
        extra_handles = []
        extra_irq_handlers = {}
        extra_hal_sources = []
        extra_hal_modules = []

        # DMA TX
        if config.dma_tx and config.mode in ("tx_rx", "tx_only"):
            mapping = self.dma_engine.lookup(f"{inst}_TX")
            if mapping:
                dma_handle = f"hdma_{inst.lower()}_tx"
                dma_info = self.dma_engine.generate_msp_dma_init(
                    mapping, handle, dma_handle, "memory_to_periph", "byte"
                )
                msp_lines.append("")
                msp_lines.append(dma_info["msp_code"])
                extra_handles.append(dma_info["handle_decl"])
                extra_irq_handlers[dma_info["irq_handler_name"]] = dma_info["irq_handler_code"]
                extra_hal_sources.extend(dma_info["hal_sources"])
                extra_hal_modules.extend(dma_info["hal_modules"])

        # DMA RX
        if config.dma_rx and config.mode in ("tx_rx", "rx_only"):
            mapping = self.dma_engine.lookup(f"{inst}_RX")
            if mapping:
                dma_handle = f"hdma_{inst.lower()}_rx"
                dma_info = self.dma_engine.generate_msp_dma_init(
                    mapping, handle, dma_handle, "periph_to_memory", "byte"
                )
                msp_lines.append("")
                msp_lines.append(dma_info["msp_code"])
                extra_handles.append(dma_info["handle_decl"])
                extra_irq_handlers[dma_info["irq_handler_name"]] = dma_info["irq_handler_code"]
                extra_hal_sources.extend(dma_info["hal_sources"])
                extra_hal_modules.extend(dma_info["hal_modules"])

        # UART IRQ enable
        if config.interrupt:
            for irq in periph.irq_names:
                msp_lines.append(f"    HAL_NVIC_SetPriority({irq}, 5, 0);")
                msp_lines.append(f"    HAL_NVIC_EnableIRQ({irq});")

        msp_lines.append("  }")

        # --- IRQ handlers ---
        irq_handlers = dict(extra_irq_handlers)
        if config.interrupt:
            for irq_name in periph.irq_names:
                handler_name = irq_name.replace("IRQn", "IRQHandler")
                irq_handlers[handler_name] = (
                    f"void {handler_name}(void)\n"
                    f"{{\n"
                    f"  HAL_UART_IRQHandler(&{handle});\n"
                    f"}}\n"
                )

        hal_sources = list(set(["stm32f4xx_hal_uart.c"] + extra_hal_sources))
        hal_modules = list(set(["HAL_UART_MODULE_ENABLED"] + extra_hal_modules))
        handles = [f"UART_HandleTypeDef {handle};"] + extra_handles

        return PeripheralCode(
            peripheral_type="uart",
            init_function=init_fn,
            init_prototype=f"static void MX_{inst}_UART_Init(void);",
            msp_init="\n".join(msp_lines),
            irq_handlers=irq_handlers,
            hal_sources=hal_sources,
            hal_modules=hal_modules,
            handle_declarations=handles,
        )
