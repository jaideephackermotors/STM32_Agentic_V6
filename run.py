#!/usr/bin/env python3
"""V6 STM32 Agent — CubeMX-free multi-agent project builder."""

import argparse
import asyncio
import sys
from pathlib import Path

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
    args = parser.parse_args()

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
        sys.exit(0)
    else:
        print(f"\nBuild FAILED at stage: {result.failed_stage}")
        print(f"Error: {result.error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
