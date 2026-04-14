"""NVIC configuration helper — not a peripheral per se, but used by all interrupt-enabled peripherals."""

from __future__ import annotations


def generate_nvic_config(irq_name: str, preempt_priority: int = 5, sub_priority: int = 0) -> str:
    """Generate NVIC priority + enable lines for an IRQ."""
    return (
        f"  HAL_NVIC_SetPriority({irq_name}, {preempt_priority}U, {sub_priority}U);\n"
        f"  HAL_NVIC_EnableIRQ({irq_name});"
    )
