"""UART/USART cookbook recipe.

Generates MX_USARTx_UART_Init(), HAL_UART_MspInit() GPIO+clock setup,
and optional IRQ handlers.
"""

from __future__ import annotations
from database.peripheral_cookbook.base import CookbookRecipe, PeripheralCode
from schemas.peripheral_config import UARTConfig
from schemas.mcu_profile import MCUProfile
from core.gpio_engine import GPIOEngine


class UARTCookbook(CookbookRecipe):
    """Deterministic UART init code generator."""

    def __init__(self, mcu: MCUProfile):
        super().__init__(mcu)
        self.gpio = GPIOEngine(mcu)

    def generate(self, config: UARTConfig) -> PeripheralCode:
        inst = config.instance  # e.g. "USART2"
        handle = f"h{'uart' if inst.startswith('UART') else 'uart'}{inst[-1]}"
        # Actually: huart2 for USART2, huart4 for UART4
        handle = f"huart{inst[-1]}"
        periph = self._find_peripheral(inst)
        is_usart = inst.startswith("USART")

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

        # --- MSP Init (GPIO + clock enable) ---
        # Determine peripheral signal names for AF lookup
        tx_signal = f"{inst}_TX"
        rx_signal = f"{inst}_RX"

        msp_lines = []
        msp_lines.append(f"  if (uartHandle->Instance == {inst})")
        msp_lines.append("  {")
        msp_lines.append(f"    {periph.rcc_macro}();")
        # TX pin GPIO port clock
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

        # TX pin
        if config.mode in ("tx_rx", "tx_only"):
            af = self.gpio.lookup_af(config.tx_pin, tx_signal)
            msp_lines.append(f"    /* {inst} TX — {config.tx_pin} */")
            msp_lines.append(f"    GPIO_InitStruct.Pin = {self._pin_number_macro(config.tx_pin)};")
            msp_lines.append("    GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;")
            msp_lines.append("    GPIO_InitStruct.Pull = GPIO_NOPULL;")
            msp_lines.append("    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;")
            msp_lines.append(f"    GPIO_InitStruct.Alternate = GPIO_AF{af}_{inst.rstrip('0123456789')};")
            msp_lines.append(f"    HAL_GPIO_Init({self._pin_port_macro(config.tx_pin)}, &GPIO_InitStruct);")

        # RX pin
        if config.mode in ("tx_rx", "rx_only"):
            af = self.gpio.lookup_af(config.rx_pin, rx_signal)
            msp_lines.append(f"    /* {inst} RX — {config.rx_pin} */")
            msp_lines.append(f"    GPIO_InitStruct.Pin = {self._pin_number_macro(config.rx_pin)};")
            msp_lines.append("    GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;")
            msp_lines.append("    GPIO_InitStruct.Pull = GPIO_NOPULL;")
            msp_lines.append("    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;")
            msp_lines.append(f"    GPIO_InitStruct.Alternate = GPIO_AF{af}_{inst.rstrip('0123456789')};")
            msp_lines.append(f"    HAL_GPIO_Init({self._pin_port_macro(config.rx_pin)}, &GPIO_InitStruct);")

        # IRQ enable
        if config.interrupt:
            for irq in periph.irq_names:
                msp_lines.append(f"    HAL_NVIC_SetPriority({irq}, 5, 0);")
                msp_lines.append(f"    HAL_NVIC_EnableIRQ({irq});")

        msp_lines.append("  }")

        # --- IRQ handlers ---
        irq_handlers = {}
        if config.interrupt:
            for irq_name in periph.irq_names:
                handler_name = irq_name.replace("IRQn", "IRQHandler")
                irq_handlers[handler_name] = (
                    f"void {handler_name}(void)\n"
                    f"{{\n"
                    f"  HAL_UART_IRQHandler(&{handle});\n"
                    f"}}\n"
                )

        return PeripheralCode(
            init_function=init_fn,
            init_prototype=f"static void MX_{inst}_UART_Init(void);",
            msp_init="\n".join(msp_lines),
            irq_handlers=irq_handlers,
            hal_sources=["stm32f4xx_hal_uart.c"],
            hal_modules=["HAL_UART_MODULE_ENABLED"],
            handle_declarations=[f"UART_HandleTypeDef {handle};"],
        )
