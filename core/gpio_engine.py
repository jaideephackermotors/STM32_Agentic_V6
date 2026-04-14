"""GPIO initialization code generator.

Generates MX_GPIO_Init() for standalone GPIOs (LEDs, buttons, etc.)
and helper functions for peripheral GPIO setup (used by cookbook recipes).
"""

from __future__ import annotations
from schemas.peripheral_config import GPIOConfig
from schemas.mcu_profile import MCUProfile, PinAF
from database.mcu.stm32f446re import GPIO_PORT_RCC


class GPIOEngine:
    """Generates GPIO initialization C code from GPIOConfig."""

    def __init__(self, mcu: MCUProfile):
        self.mcu = mcu
        # Build lookup: (pin, peripheral_signal) → AF number
        self._af_lookup: dict[tuple[str, str], int] = {}
        for af in mcu.pin_af_table:
            self._af_lookup[(af.pin, af.peripheral)] = af.af

    def lookup_af(self, pin: str, peripheral_signal: str) -> int | None:
        """Find the AF number for a pin/peripheral combination.

        Args:
            pin: e.g. "PA2"
            peripheral_signal: e.g. "USART2_TX"

        Returns:
            AF number (0-15) or None if not found.
        """
        return self._af_lookup.get((pin, peripheral_signal))

    def pin_port(self, pin: str) -> str:
        """Extract port letter from pin name. PA5 → A"""
        return pin[1]

    def pin_number(self, pin: str) -> int:
        """Extract pin number from pin name. PA5 → 5"""
        return int(pin[2:])

    def generate_standalone_init(self, gpios: list[GPIOConfig]) -> str:
        """Generate MX_GPIO_Init() function for standalone GPIOs."""
        if not gpios:
            return self._empty_gpio_init()

        lines = []
        lines.append("static void MX_GPIO_Init(void)")
        lines.append("{")
        lines.append("  GPIO_InitTypeDef GPIO_InitStruct = {0};")
        lines.append("")

        # Enable clocks for all used ports
        ports_used = sorted(set(self.pin_port(g.pin) for g in gpios))
        for port in ports_used:
            rcc = GPIO_PORT_RCC.get(port)
            if rcc:
                lines.append(f"  {rcc}();")
        lines.append("")

        # Set output initial states before configuring as output
        for gpio in gpios:
            if gpio.mode.startswith("output"):
                state = "GPIO_PIN_SET" if gpio.initial_state == "high" else "GPIO_PIN_RESET"
                lines.append(
                    f"  HAL_GPIO_WritePin(GPIO{self.pin_port(gpio.pin)}, "
                    f"GPIO_PIN_{self.pin_number(gpio.pin)}, {state});"
                )
        lines.append("")

        # Configure each pin
        for gpio in gpios:
            mode_map = {
                "output_pp": "GPIO_MODE_OUTPUT_PP",
                "output_od": "GPIO_MODE_OUTPUT_OD",
                "input": "GPIO_MODE_INPUT",
                "input_pullup": "GPIO_MODE_INPUT",
                "input_pulldown": "GPIO_MODE_INPUT",
                "analog": "GPIO_MODE_ANALOG",
            }
            pull_map = {
                "input_pullup": "GPIO_PULLUP",
                "input_pulldown": "GPIO_PULLDOWN",
            }
            speed_map = {
                "low": "GPIO_SPEED_FREQ_LOW",
                "medium": "GPIO_SPEED_FREQ_MEDIUM",
                "high": "GPIO_SPEED_FREQ_HIGH",
                "very_high": "GPIO_SPEED_FREQ_VERY_HIGH",
            }

            port = self.pin_port(gpio.pin)
            pin_num = self.pin_number(gpio.pin)
            mode = mode_map[gpio.mode]
            pull = pull_map.get(gpio.mode, "GPIO_NOPULL")
            speed = speed_map[gpio.speed]

            if gpio.label:
                lines.append(f"  /* {gpio.label} — {gpio.pin} */")

            lines.append(f"  GPIO_InitStruct.Pin = GPIO_PIN_{pin_num};")
            lines.append(f"  GPIO_InitStruct.Mode = {mode};")
            lines.append(f"  GPIO_InitStruct.Pull = {pull};")
            if gpio.mode.startswith("output"):
                lines.append(f"  GPIO_InitStruct.Speed = {speed};")
            lines.append(f"  HAL_GPIO_Init(GPIO{port}, &GPIO_InitStruct);")
            lines.append("")

        lines.append("}")
        return "\n".join(lines)

    def generate_peripheral_gpio(
        self, pin: str, peripheral_signal: str, pull: str = "GPIO_NOPULL"
    ) -> str:
        """Generate GPIO init code for a peripheral pin (AF mode).

        Used by cookbook recipes to set up TX/RX/SCK/etc. pins.
        Returns a block of C code (no function wrapper).
        """
        port = self.pin_port(pin)
        pin_num = self.pin_number(pin)
        af = self.lookup_af(pin, peripheral_signal)
        if af is None:
            raise ValueError(f"No AF mapping for {pin} → {peripheral_signal}")

        return (
            f"  GPIO_InitStruct.Pin = GPIO_PIN_{pin_num};\n"
            f"  GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;\n"
            f"  GPIO_InitStruct.Pull = {pull};\n"
            f"  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;\n"
            f"  GPIO_InitStruct.Alternate = GPIO_AF{af}_{''.join(c for c in peripheral_signal.split('_')[0] if c.isalpha())};\n"
            f"  HAL_GPIO_Init(GPIO{port}, &GPIO_InitStruct);\n"
        )

    def get_port_rcc_enable(self, pin: str) -> str:
        """Return the RCC clock enable call for a pin's GPIO port."""
        port = self.pin_port(pin)
        rcc = GPIO_PORT_RCC.get(port, f"__HAL_RCC_GPIO{port}_CLK_ENABLE")
        return f"  {rcc}();"

    def _empty_gpio_init(self) -> str:
        return (
            "static void MX_GPIO_Init(void)\n"
            "{\n"
            "  /* No standalone GPIOs configured */\n"
            "}\n"
        )
