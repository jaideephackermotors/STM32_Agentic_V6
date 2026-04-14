"""Identifier validator — anti-hallucination vocabulary lock.

Checks that all identifiers in LLM-generated code exist in the
vocabulary extracted from the generated project files.
"""

from __future__ import annotations
import re
from dataclasses import dataclass


@dataclass
class IdentifierViolation:
    identifier: str
    context: str
    suggestion: str = ""


# Standard C / CMSIS identifiers always valid
ALWAYS_VALID_PREFIXES = (
    "uint", "int", "void", "char", "float", "double", "size_t", "bool",
    "NULL", "true", "false", "sizeof", "volatile", "static", "const",
    "extern", "struct", "enum", "typedef", "return", "if", "else",
    "while", "for", "do", "switch", "case", "break", "continue", "default",
    "__disable_irq", "__enable_irq", "__NOP", "__WFI", "__WFE",
    "SCB", "NVIC", "SysTick", "ITM",
    "HAL_OK", "HAL_ERROR", "HAL_BUSY", "HAL_TIMEOUT",
    "HAL_Init", "HAL_Delay", "HAL_GetTick", "HAL_IncTick",
    "Error_Handler",
    "GPIO_PIN_SET", "GPIO_PIN_RESET",
    "ENABLE", "DISABLE",
)

# Regex for HAL function calls
HAL_FUNC_RE = re.compile(r"\bHAL_\w+")
# Regex for handle variables
HANDLE_RE = re.compile(r"\bh(?:uart|tim|spi|i2c|adc|dma|dac|can)\d+\b")
# Regex for pin defines
PIN_DEFINE_RE = re.compile(r"\b\w+_(?:Pin|GPIO_Port)\b")
# Regex for IRQ handler names
IRQ_RE = re.compile(r"\b\w+_IRQHandler\b")


class IdentifierValidator:
    """Validates LLM-generated code against a known vocabulary."""

    def __init__(self, vocabulary: dict):
        """Initialize with vocabulary extracted from generated code.

        vocabulary keys: "handles", "hal_functions", "pin_defines",
                        "irq_handlers", "peripheral_instances"
        """
        self.handles = set(vocabulary.get("handles", []))
        self.hal_functions = set(vocabulary.get("hal_functions", []))
        self.pin_defines = set(vocabulary.get("pin_defines", []))
        self.irq_handlers = set(vocabulary.get("irq_handlers", []))
        self.instances = set(vocabulary.get("peripheral_instances", []))

    def validate(self, code: str) -> list[IdentifierViolation]:
        """Check all identifiers in the code against vocabulary."""
        violations = []

        # Check HAL function calls
        for match in HAL_FUNC_RE.finditer(code):
            func = match.group()
            if func not in self.hal_functions and not self._is_always_valid(func):
                violations.append(IdentifierViolation(
                    identifier=func,
                    context="HAL function call",
                    suggestion=self._suggest_similar(func, self.hal_functions),
                ))

        # Check handles
        for match in HANDLE_RE.finditer(code):
            handle = match.group()
            if handle not in self.handles:
                violations.append(IdentifierViolation(
                    identifier=handle,
                    context="peripheral handle",
                    suggestion=f"Valid handles: {', '.join(sorted(self.handles))}",
                ))

        # Check pin defines
        for match in PIN_DEFINE_RE.finditer(code):
            define = match.group()
            if define not in self.pin_defines and not self._is_always_valid(define):
                violations.append(IdentifierViolation(
                    identifier=define,
                    context="pin define",
                    suggestion=f"Valid defines: {', '.join(sorted(self.pin_defines))}",
                ))

        return violations

    def _is_always_valid(self, ident: str) -> bool:
        return any(ident.startswith(p) for p in ALWAYS_VALID_PREFIXES)

    def _suggest_similar(self, target: str, candidates: set[str]) -> str:
        """Find the most similar valid identifier."""
        if not candidates:
            return ""
        # Simple prefix matching
        prefix = target[:10]
        matches = [c for c in candidates if c.startswith(prefix[:6])]
        if matches:
            return f"Did you mean: {', '.join(sorted(matches)[:3])}?"
        return ""
