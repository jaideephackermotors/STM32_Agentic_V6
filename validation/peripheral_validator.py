"""Peripheral existence and AF validator."""

from __future__ import annotations
from dataclasses import dataclass

from schemas.blueprint import ProjectBlueprint
from schemas.mcu_profile import MCUProfile
from core.gpio_engine import GPIOEngine


@dataclass
class PeripheralError:
    severity: str
    message: str


class PeripheralValidator:
    """Validates that all peripherals and pin-AF mappings in blueprint exist on the MCU."""

    def __init__(self, mcu: MCUProfile):
        self.mcu = mcu
        self.gpio = GPIOEngine(mcu)
        self._peripheral_names = {p.name for p in mcu.peripherals}

    def validate(self, blueprint: ProjectBlueprint) -> list[PeripheralError]:
        errors = []

        # Check UART instances exist
        for uart in blueprint.uarts:
            if uart.instance not in self._peripheral_names:
                errors.append(PeripheralError("ERROR", f"{uart.instance} does not exist on {self.mcu.name}"))
            else:
                self._check_af(errors, uart.tx_pin, f"{uart.instance}_TX")
                self._check_af(errors, uart.rx_pin, f"{uart.instance}_RX")

        # Check SPI instances
        for spi in blueprint.spis:
            if spi.instance not in self._peripheral_names:
                errors.append(PeripheralError("ERROR", f"{spi.instance} does not exist on {self.mcu.name}"))
            else:
                self._check_af(errors, spi.sck_pin, f"{spi.instance}_SCK")
                self._check_af(errors, spi.mosi_pin, f"{spi.instance}_MOSI")
                self._check_af(errors, spi.miso_pin, f"{spi.instance}_MISO")

        # Check I2C instances
        for i2c in blueprint.i2cs:
            if i2c.instance not in self._peripheral_names:
                errors.append(PeripheralError("ERROR", f"{i2c.instance} does not exist on {self.mcu.name}"))
            else:
                self._check_af(errors, i2c.scl_pin, f"{i2c.instance}_SCL")
                self._check_af(errors, i2c.sda_pin, f"{i2c.instance}_SDA")

        # Check timer instances and channels
        for tim in blueprint.timers:
            if tim.instance not in self._peripheral_names:
                errors.append(PeripheralError("ERROR", f"{tim.instance} does not exist on {self.mcu.name}"))
            else:
                # Check channel count
                tim_info = next((t for t in self.mcu.timers if t.name == tim.instance), None)
                if tim_info:
                    for ch in tim.channels:
                        if ch.channel > tim_info.channels:
                            errors.append(PeripheralError(
                                "ERROR",
                                f"{tim.instance} has {tim_info.channels} channels, but CH{ch.channel} requested"
                            ))
                        else:
                            self._check_af(errors, ch.pin, f"{tim.instance}_CH{ch.channel}")

        # Check ADC instances
        for adc in blueprint.adcs:
            if adc.instance not in self._peripheral_names:
                errors.append(PeripheralError("ERROR", f"{adc.instance} does not exist on {self.mcu.name}"))

        return errors

    def _check_af(self, errors: list, pin: str, signal: str):
        """Check that pin has an AF mapping for the given peripheral signal."""
        af = self.gpio.lookup_af(pin, signal)
        if af is None:
            errors.append(PeripheralError(
                "ERROR",
                f"No AF mapping: {pin} → {signal}. Check datasheet Table 12."
            ))
