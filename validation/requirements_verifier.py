"""Requirements verifier — injects static_assert for numeric requirements."""

from __future__ import annotations
from dataclasses import dataclass

from schemas.peripheral_config import ClockConfig


@dataclass
class RequirementAssertion:
    req_id: str
    description: str
    c_expression: str
    expected: str


class RequirementsVerifier:
    """Generates static_assert expressions to prove requirements at compile time."""

    def verify_clock(self, clock: ClockConfig, req_id: str = "CLK") -> list[RequirementAssertion]:
        """Generate assertions for clock configuration."""
        assertions = []

        # Verify SYSCLK
        pll_m = clock.pll_m
        pll_n = clock.pll_n
        pll_p = clock.pll_p
        hse = clock.hse_mhz

        assertions.append(RequirementAssertion(
            req_id=f"{req_id}-SYSCLK",
            description=f"SYSCLK = {clock.sysclk_mhz}MHz",
            c_expression=f"(({hse}U * {pll_n}U) / ({pll_m}U * {pll_p}U)) == {clock.sysclk_mhz}U",
            expected=f"{clock.sysclk_mhz}",
        ))

        # Verify APB1
        assertions.append(RequirementAssertion(
            req_id=f"{req_id}-APB1",
            description=f"APB1 = {clock.apb1_mhz}MHz",
            c_expression=f"({clock.sysclk_mhz}U / {clock.apb1_prescaler}U) == {clock.apb1_mhz}U",
            expected=f"{clock.apb1_mhz}",
        ))

        return assertions

    def verify_timer_tick(
        self,
        timer_name: str,
        prescaler: int,
        timer_clk_mhz: int,
        expected_tick_hz: int,
        req_id: str = "TIM",
    ) -> RequirementAssertion:
        """Verify timer tick rate: tick_hz = timer_clk / (PSC + 1)."""
        clk_hz = timer_clk_mhz * 1_000_000
        return RequirementAssertion(
            req_id=f"{req_id}-{timer_name}-TICK",
            description=f"{timer_name} tick = {expected_tick_hz}Hz",
            c_expression=f"({clk_hz}U / ({prescaler}U + 1U)) == {expected_tick_hz}U",
            expected=str(expected_tick_hz),
        )

    def generate_c_block(self, assertions: list[RequirementAssertion]) -> str:
        """Generate a block of static_assert statements."""
        lines = ["/* Compile-time requirement verification */"]
        for a in assertions:
            lines.append(f"/* {a.req_id}: {a.description} */")
            lines.append(f'_Static_assert({a.c_expression}, "{a.req_id}: {a.description}");')
        return "\n".join(lines)
