"""Pin conflict validator — ensures no two peripherals claim the same pin."""

from __future__ import annotations
from dataclasses import dataclass

from schemas.blueprint import ProjectBlueprint


@dataclass
class PinConflict:
    pin: str
    users: list[str]


class PinConflictValidator:
    """Detects GPIO pin conflicts in a blueprint."""

    def validate(self, blueprint: ProjectBlueprint) -> list[PinConflict]:
        """Check for pins used by multiple peripherals."""
        pin_users: dict[str, list[str]] = {}

        def _record(pin: str, user: str):
            pin_users.setdefault(pin, []).append(user)

        # Standalone GPIOs
        for gpio in blueprint.gpios:
            _record(gpio.pin, f"GPIO:{gpio.label or gpio.pin}")

        # UARTs
        for uart in blueprint.uarts:
            if uart.mode in ("tx_rx", "tx_only"):
                _record(uart.tx_pin, f"{uart.instance}_TX")
            if uart.mode in ("tx_rx", "rx_only"):
                _record(uart.rx_pin, f"{uart.instance}_RX")

        # SPIs
        for spi in blueprint.spis:
            _record(spi.sck_pin, f"{spi.instance}_SCK")
            _record(spi.mosi_pin, f"{spi.instance}_MOSI")
            _record(spi.miso_pin, f"{spi.instance}_MISO")
            if spi.nss_pin:
                _record(spi.nss_pin, f"{spi.instance}_NSS")

        # I2Cs
        for i2c in blueprint.i2cs:
            _record(i2c.scl_pin, f"{i2c.instance}_SCL")
            _record(i2c.sda_pin, f"{i2c.instance}_SDA")

        # Timers (channels)
        for tim in blueprint.timers:
            for ch in tim.channels:
                _record(ch.pin, f"{tim.instance}_CH{ch.channel}")

        # ADCs
        for adc in blueprint.adcs:
            for ch in adc.channels:
                if ch.pin and ch.pin != "internal":
                    _record(ch.pin, f"{adc.instance}_CH{ch.channel}")

        # Find conflicts
        conflicts = []
        for pin, users in pin_users.items():
            if len(users) > 1:
                conflicts.append(PinConflict(pin=pin, users=users))

        return conflicts
