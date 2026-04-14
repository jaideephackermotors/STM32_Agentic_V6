"""Input capture timer cookbook recipe."""

from __future__ import annotations
from database.peripheral_cookbook.base import CookbookRecipe, PeripheralCode
from schemas.peripheral_config import TimerConfig
from schemas.mcu_profile import MCUProfile
from core.gpio_engine import GPIOEngine


class TimerICCookbook(CookbookRecipe):
    """Generates timer init with input capture channels."""

    def __init__(self, mcu: MCUProfile):
        super().__init__(mcu)
        self.gpio = GPIOEngine(mcu)

    def generate(self, config: TimerConfig) -> PeripheralCode:
        inst = config.instance
        handle = f"htim{inst.replace('TIM', '').lower()}"
        periph = self._find_peripheral(inst)

        # Build IC channel config blocks
        ch_blocks = []
        for ch in config.channels:
            pol_map = {
                "rising": "TIM_INPUTCHANNELPOLARITY_RISING",
                "falling": "TIM_INPUTCHANNELPOLARITY_FALLING",
                "both": "TIM_INPUTCHANNELPOLARITY_BOTHEDGE",
            }
            pol = pol_map.get(ch.polarity, "TIM_INPUTCHANNELPOLARITY_RISING")
            ch_blocks.append(
                f"  sConfigIC.ICPolarity = {pol};\n"
                f"  sConfigIC.ICSelection = TIM_ICSELECTION_DIRECTTI;\n"
                f"  sConfigIC.ICPrescaler = TIM_ICPSC_DIV1;\n"
                f"  sConfigIC.ICFilter = {ch.ic_filter}U;\n"
                f"  if (HAL_TIM_IC_ConfigChannel(&{handle}, &sConfigIC, TIM_CHANNEL_{ch.channel}) != HAL_OK)\n"
                f"  {{\n"
                f"    Error_Handler();\n"
                f"  }}"
            )

        ch_code = "\n\n".join(ch_blocks)

        init_fn = f"""\
static void MX_{inst}_Init(void)
{{
  TIM_ClockConfigTypeDef sClockSourceConfig = {{0}};
  TIM_IC_InitTypeDef sConfigIC = {{0}};

  {handle}.Instance = {inst};
  {handle}.Init.Prescaler = {config.prescaler}U;
  {handle}.Init.CounterMode = TIM_COUNTERMODE_UP;
  {handle}.Init.Period = {config.period}U;
  {handle}.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  {handle}.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&{handle}) != HAL_OK)
  {{
    Error_Handler();
  }}

  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&{handle}, &sClockSourceConfig) != HAL_OK)
  {{
    Error_Handler();
  }}

  if (HAL_TIM_IC_Init(&{handle}) != HAL_OK)
  {{
    Error_Handler();
  }}

{ch_code}
}}"""

        # MSP init
        msp_lines = [
            f"  if (htimHandle->Instance == {inst})",
            "  {",
            f"    {periph.rcc_macro}();",
        ]
        ports = set()
        for ch in config.channels:
            ports.add(ch.pin[1])
        for port in sorted(ports):
            from database.mcu.stm32f446re import GPIO_PORT_RCC
            msp_lines.append(f"    {GPIO_PORT_RCC[port]}();")

        msp_lines.append("")
        msp_lines.append("    GPIO_InitTypeDef GPIO_InitStruct = {0};")

        for ch in config.channels:
            signal = f"{inst}_CH{ch.channel}"
            af = self.gpio.lookup_af(ch.pin, signal)
            msp_lines.append(f"    /* {signal} — {ch.pin} */")
            msp_lines.append(f"    GPIO_InitStruct.Pin = {self._pin_number_macro(ch.pin)};")
            msp_lines.append("    GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;")
            msp_lines.append("    GPIO_InitStruct.Pull = GPIO_NOPULL;")
            msp_lines.append("    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;")
            msp_lines.append(f"    GPIO_InitStruct.Alternate = GPIO_AF{af}_TIM{inst.replace('TIM', '')};")
            msp_lines.append(f"    HAL_GPIO_Init({self._pin_port_macro(ch.pin)}, &GPIO_InitStruct);")

        if config.interrupt:
            for irq in periph.irq_names:
                msp_lines.append(f"    HAL_NVIC_SetPriority({irq}, 5, 0);")
                msp_lines.append(f"    HAL_NVIC_EnableIRQ({irq});")

        msp_lines.append("  }")

        irq_handlers = {}
        if config.interrupt:
            for irq_name in periph.irq_names:
                handler = irq_name.replace("IRQn", "IRQHandler")
                irq_handlers[handler] = (
                    f"void {handler}(void)\n"
                    f"{{\n"
                    f"  HAL_TIM_IRQHandler(&{handle});\n"
                    f"}}\n"
                )

        return PeripheralCode(
            peripheral_type="timer",
            init_function=init_fn,
            init_prototype=f"static void MX_{inst}_Init(void);",
            msp_init="\n".join(msp_lines),
            irq_handlers=irq_handlers,
            hal_sources=["stm32f4xx_hal_tim.c", "stm32f4xx_hal_tim_ex.c"],
            hal_modules=["HAL_TIM_MODULE_ENABLED"],
            handle_declarations=[f"TIM_HandleTypeDef {handle};"],
        )
