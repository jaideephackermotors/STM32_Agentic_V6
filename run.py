#!/usr/bin/env python3
"""V6 STM32 Agent — CubeMX-free multi-agent project builder."""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env file if present
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.isfile(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _val.strip())

from agents.orchestrator import Orchestrator


def main():
    parser = argparse.ArgumentParser(
        description="Generate STM32 projects from natural language requirements"
    )
    parser.add_argument(
        "requirements",
        help="Natural language requirements string or path to .txt file",
    )
    parser.add_argument(
        "--mcu",
        default="STM32F446RETx",
        help="Target MCU (default: STM32F446RETx)",
    )
    parser.add_argument(
        "--output",
        default="./generated",
        help="Output directory (default: ./generated)",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Config file path (default: config.yaml)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # If requirements is a file path, read it
    req_path = Path(args.requirements)
    if req_path.is_file():
        requirements = req_path.read_text(encoding="utf-8")
    else:
        requirements = args.requirements

    orchestrator = Orchestrator(
        config_path=args.config,
        mcu_name=args.mcu,
        output_dir=args.output,
    )
    result = asyncio.run(orchestrator.run(requirements))

    if result.success:
        print(f"\nBuild SUCCESS: {result.elf_path}")
        print(f"Flash: {result.flash_size} bytes | RAM: {result.ram_size} bytes")
        if result.emulation_result:
            emu = result.emulation_result
            print(f"\nEmulation: {emu.get('status', '?')} ({emu.get('duration_ms', 0)}ms)")
            for c in emu.get("checks", []):
                icon = "+" if c["passed"] else "-"
                print(f"  [{icon}] {c['check']}: {c['detail'][:70]}")
            if emu.get("uart_output"):
                print(f"  UART: {emu['uart_output'][:100]!r}")
        sys.exit(0)
    else:
        print(f"\nBuild FAILED at stage: {result.failed_stage}")
        print(f"Error: {result.error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
