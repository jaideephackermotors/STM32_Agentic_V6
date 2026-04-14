"""Clock configuration validator."""

from __future__ import annotations
from dataclasses import dataclass

from schemas.peripheral_config import ClockConfig
from schemas.mcu_profile import MCUProfile


@dataclass
class ValidationError:
    severity: str   # "ERROR" or "WARNING"
    message: str


class ClockValidator:
    """Validates clock configuration against MCU limits."""

    def __init__(self, mcu: MCUProfile):
        self.mcu = mcu

    def validate(self, clock: ClockConfig) -> list[ValidationError]:
        errors = []

        # SYSCLK limit
        if clock.sysclk_mhz > self.mcu.max_sysclk_mhz:
            errors.append(ValidationError(
                "ERROR",
                f"SYSCLK {clock.sysclk_mhz}MHz exceeds max {self.mcu.max_sysclk_mhz}MHz"
            ))

        # APB1 limit
        if clock.apb1_mhz > self.mcu.max_apb1_mhz:
            errors.append(ValidationError(
                "ERROR",
                f"APB1 {clock.apb1_mhz}MHz exceeds max {self.mcu.max_apb1_mhz}MHz"
            ))

        # APB2 limit
        if clock.apb2_mhz > self.mcu.max_apb2_mhz:
            errors.append(ValidationError(
                "ERROR",
                f"APB2 {clock.apb2_mhz}MHz exceeds max {self.mcu.max_apb2_mhz}MHz"
            ))

        # PLL constraints
        vco_input = clock.hse_mhz / clock.pll_m
        if not (1.0 <= vco_input <= 2.0):
            errors.append(ValidationError(
                "ERROR",
                f"VCO input {vco_input:.1f}MHz out of range [1, 2]MHz"
            ))

        vco_output = vco_input * clock.pll_n
        if not (100.0 <= vco_output <= 432.0):
            errors.append(ValidationError(
                "ERROR",
                f"VCO output {vco_output:.1f}MHz out of range [100, 432]MHz"
            ))

        if clock.pll_p not in (2, 4, 6, 8):
            errors.append(ValidationError("ERROR", f"PLL_P={clock.pll_p} invalid, must be 2/4/6/8"))

        # Verify derived clocks are consistent
        expected_sysclk = int(vco_output / clock.pll_p)
        if abs(clock.sysclk_mhz - expected_sysclk) > 1:
            errors.append(ValidationError(
                "WARNING",
                f"SYSCLK mismatch: config says {clock.sysclk_mhz}MHz but PLL math gives {expected_sysclk}MHz"
            ))

        return errors
