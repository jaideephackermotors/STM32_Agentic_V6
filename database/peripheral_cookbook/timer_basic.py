"""Basic timer cookbook — periodic interrupts, timebase."""

from __future__ import annotations
from database.peripheral_cookbook.base import CookbookRecipe, PeripheralCode
from schemas.peripheral_config import TimerConfig
from schemas.mcu_profile import MCUProfile


class TimerBasicCookbook(CookbookRecipe):
    """Generates basic timer init (no channels, just overflow interrupt)."""

    def generate(self, config: TimerConfig) -> PeripheralCode:
        inst = config.instance
        handle = f"htim{inst.replace('TIM', '').lower()}"
        periph = self._find_peripheral(inst)

        init_fn = f"""\
static void MX_{inst}_Init(void)
{{
  TIM_ClockConfigTypeDef sClockSourceConfig = {{0}};
  TIM_MasterConfigTypeDef sMasterConfig = {{0}};

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

  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&{handle}, &sMasterConfig) != HAL_OK)
  {{
    Error_Handler();
  }}
}}"""

        # MSP init
        msp = (
            f"  if (htimHandle->Instance == {inst})\n"
            f"  {{\n"
            f"    {periph.rcc_macro}();\n"
        )
        if config.interrupt:
            for irq in periph.irq_names:
                msp += f"    HAL_NVIC_SetPriority({irq}, 5, 0);\n"
                msp += f"    HAL_NVIC_EnableIRQ({irq});\n"
        msp += "  }"

        # IRQ handlers
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
            msp_init=msp,
            irq_handlers=irq_handlers,
            hal_sources=["stm32f4xx_hal_tim.c", "stm32f4xx_hal_tim_ex.c"],
            hal_modules=["HAL_TIM_MODULE_ENABLED"],
            handle_declarations=[f"TIM_HandleTypeDef {handle};"],
        )
