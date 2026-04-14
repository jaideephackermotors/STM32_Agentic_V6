"""I2C cookbook recipe."""

from __future__ import annotations
from database.peripheral_cookbook.base import CookbookRecipe, PeripheralCode
from schemas.peripheral_config import I2CConfig
from schemas.mcu_profile import MCUProfile
from core.gpio_engine import GPIOEngine


class I2CCookbook(CookbookRecipe):
    """Generates I2C peripheral init code."""

    def __init__(self, mcu: MCUProfile):
        super().__init__(mcu)
        self.gpio = GPIOEngine(mcu)

    def generate(self, config: I2CConfig) -> PeripheralCode:
        inst = config.instance
        handle = f"hi2c{inst[-1]}"
        periph = self._find_peripheral(inst)

        duty = "I2C_DUTYCYCLE_2" if config.duty_cycle == "2" else "I2C_DUTYCYCLE_16_9"

        init_fn = f"""\
static void MX_{inst}_Init(void)
{{
  {handle}.Instance = {inst};
  {handle}.Init.ClockSpeed = {config.clock_speed}U;
  {handle}.Init.DutyCycle = {duty};
  {handle}.Init.OwnAddress1 = 0U;
  {handle}.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
  {handle}.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
  {handle}.Init.OwnAddress2 = 0U;
  {handle}.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
  {handle}.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE;
  if (HAL_I2C_Init(&{handle}) != HAL_OK)
  {{
    Error_Handler();
  }}
}}"""

        # MSP
        msp_lines = [
            f"  if (i2cHandle->Instance == {inst})",
            "  {",
            f"    {periph.rcc_macro}();",
        ]
        pins = [(config.scl_pin, f"{inst}_SCL"), (config.sda_pin, f"{inst}_SDA")]
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
            msp_lines.append("    GPIO_InitStruct.Mode = GPIO_MODE_AF_OD;")
            msp_lines.append("    GPIO_InitStruct.Pull = GPIO_PULLUP;")
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
            hal_sources=["stm32f4xx_hal_i2c.c", "stm32f4xx_hal_i2c_ex.c"],
            hal_modules=["HAL_I2C_MODULE_ENABLED"],
            handle_declarations=[f"I2C_HandleTypeDef {handle};"],
        )
