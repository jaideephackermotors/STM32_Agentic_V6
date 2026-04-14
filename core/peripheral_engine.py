"""Peripheral engine — orchestrates cookbook recipes to generate all init code."""

from __future__ import annotations
from schemas.blueprint import ProjectBlueprint
from schemas.mcu_profile import MCUProfile
from database.peripheral_cookbook.base import PeripheralCode
from database.peripheral_cookbook.gpio import GPIOCookbook
from database.peripheral_cookbook.uart import UARTCookbook
from database.peripheral_cookbook.spi import SPICookbook
from database.peripheral_cookbook.i2c import I2CCookbook
from database.peripheral_cookbook.timer_basic import TimerBasicCookbook
from database.peripheral_cookbook.timer_pwm import TimerPWMCookbook
from database.peripheral_cookbook.timer_input_capture import TimerICCookbook
from database.peripheral_cookbook.adc import ADCCookbook


class PeripheralEngine:
    """Runs all cookbook recipes for a blueprint, collects generated code."""

    def __init__(self, mcu: MCUProfile):
        self.mcu = mcu
        self.gpio_cookbook = GPIOCookbook(mcu)
        self.uart_cookbook = UARTCookbook(mcu)
        self.spi_cookbook = SPICookbook(mcu)
        self.i2c_cookbook = I2CCookbook(mcu)
        self.timer_basic = TimerBasicCookbook(mcu)
        self.timer_pwm = TimerPWMCookbook(mcu)
        self.timer_ic = TimerICCookbook(mcu)
        self.adc_cookbook = ADCCookbook(mcu)

    def generate_all(self, blueprint: ProjectBlueprint) -> list[PeripheralCode]:
        """Run all relevant cookbook recipes, return list of PeripheralCode."""
        results: list[PeripheralCode] = []

        # GPIO (standalone pins)
        if blueprint.gpios:
            results.append(self.gpio_cookbook.generate(blueprint.gpios))

        # UARTs
        for uart in blueprint.uarts:
            results.append(self.uart_cookbook.generate(uart))

        # SPIs
        for spi in blueprint.spis:
            results.append(self.spi_cookbook.generate(spi))

        # I2Cs
        for i2c in blueprint.i2cs:
            results.append(self.i2c_cookbook.generate(i2c))

        # Timers — dispatch to correct cookbook by mode
        for tim in blueprint.timers:
            if tim.mode == "pwm":
                results.append(self.timer_pwm.generate(tim))
            elif tim.mode == "input_capture":
                results.append(self.timer_ic.generate(tim))
            else:
                results.append(self.timer_basic.generate(tim))

        # ADCs
        for adc in blueprint.adcs:
            results.append(self.adc_cookbook.generate(adc))

        return results

    def collect_hal_modules(self, codes: list[PeripheralCode]) -> list[str]:
        """Collect unique HAL module enable macros from all generated code."""
        modules = set()
        for code in codes:
            modules.update(code.hal_modules)
        return sorted(modules)

    def collect_hal_sources(self, codes: list[PeripheralCode]) -> list[str]:
        """Collect unique HAL .c source files needed."""
        sources = set()
        for code in codes:
            sources.update(code.hal_sources)
        return sorted(sources)

    def collect_handles(self, codes: list[PeripheralCode]) -> list[str]:
        """Collect all handle declarations."""
        handles = []
        for code in codes:
            handles.extend(code.handle_declarations)
        return handles

    def collect_init_prototypes(self, codes: list[PeripheralCode]) -> list[str]:
        """Collect all init function prototypes."""
        protos = []
        for code in codes:
            if code.init_prototype:
                protos.append(code.init_prototype)
        return protos

    def collect_init_functions(self, codes: list[PeripheralCode]) -> list[str]:
        """Collect all init function bodies."""
        fns = []
        for code in codes:
            if code.init_function:
                fns.append(code.init_function)
        return fns

    def collect_msp_inits(self, codes: list[PeripheralCode]) -> list[str]:
        """Collect all MSP init blocks."""
        msps = []
        for code in codes:
            if code.msp_init:
                msps.append(code.msp_init)
        return msps

    def collect_irq_handlers(self, codes: list[PeripheralCode]) -> dict[str, str]:
        """Collect all IRQ handler functions."""
        handlers = {}
        for code in codes:
            handlers.update(code.irq_handlers)
        return handlers
