"""PWM timer cookbook recipe."""

from __future__ import annotations
from database.peripheral_cookbook.base import CookbookRecipe, PeripheralCode
from schemas.peripheral_config import TimerConfig
from schemas.mcu_profile import MCUProfile
from core.gpio_engine import GPIOEngine


class TimerPWMCookbook(CookbookRecipe):
    """Generates timer init with PWM output channels."""

    def __init__(self, mcu: MCUProfile):
        super().__init__(mcu)
        self.gpio = GPIOEngine(mcu)

    def generate(self, config: TimerConfig) -> PeripheralCode:
        inst = config.instance
        handle = f"htim{inst.replace('TIM', '').lower()}"
        periph = self._find_peripheral(inst)

        # Build channel config blocks
        ch_blocks = []
        for ch in config.channels:
            ch_blocks.append(
                f"  sConfigOC.OCMode = TIM_OCMODE_PWM1;\n"
                f"  sConfigOC.Pulse = {ch.pulse}U;\n"
                f"  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;\n"
                f"  sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;\n"
                f"  if (HAL_TIM_PWM_ConfigChannel(&{handle}, &sConfigOC, TIM_CHANNEL_{ch.channel}) != HAL_OK)\n"
                f"  {{\n"
                f"    Error_Handler();\n"
                f"  }}"
            )

        ch_code = "\n\n".join(ch_blocks)

        init_fn = f"""\
static void MX_{inst}_Init(void)
{{
  TIM_ClockConfigTypeDef sClockSourceConfig = {{0}};
  TIM_MasterConfigTypeDef sMasterConfig = {{0}};
  TIM_OC_InitTypeDef sConfigOC = {{0}};

  {handle}.Instance = {inst};
  {handle}.Init.Prescaler = {config.prescaler}U;
  {handle}.Init.CounterMode = TIM_COUNTERMODE_UP;
  {handle}.Init.Period = {config.period}U;
  {handle}.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  {handle}.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;
  if (HAL_TIM_Base_Init(&{handle}) != HAL_OK)
  {{
    Error_Handler();
  }}

  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&{handle}, &sClockSourceConfig) != HAL_OK)
  {{
    Error_Handler();
  }}

  if (HAL_TIM_PWM_Init(&{handle}) != HAL_OK)
  {{
    Error_Handler();
  }}

  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&{handle}, &sMasterConfig) != HAL_OK)
  {{
    Error_Handler();
  }}

{ch_code}
}}"""

        # MSP: clock enable + GPIO AF for each channel pin
        msp_lines = [
            f"  if (htimHandle->Instance == {inst})",
            "  {",
            f"    {periph.rcc_macro}();",
        ]
        # GPIO ports
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
            msp_lines.append(f"    GPIO_InitStruct.Alternate = GPIO_AF{af}_TIM{inst.replace('TIM', '')};")  # noqa
            msp_lines.append(f"    HAL_GPIO_Init({self._pin_port_macro(ch.pin)}, &GPIO_InitStruct);")

        msp_lines.append("  }")

        return PeripheralCode(
            peripheral_type="timer",
            init_function=init_fn,
            init_prototype=f"static void MX_{inst}_Init(void);",
            msp_init="\n".join(msp_lines),
            hal_sources=["stm32f4xx_hal_tim.c", "stm32f4xx_hal_tim_ex.c"],
            hal_modules=["HAL_TIM_MODULE_ENABLED"],
            handle_declarations=[f"TIM_HandleTypeDef {handle};"],
        )
