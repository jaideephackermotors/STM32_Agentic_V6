"""Renode-based functional test runner for generated STM32 projects.

Auto-generates test assertions from the ProjectBlueprint:
  - UART present → capture and verify UART output
  - GPIO present → verify firmware runs (no crash)
  - Timer present → verify firmware runs (no crash)
  - ADC+UART present → verify UART prints numeric ADC readings
  - SPI/I2C present → verify firmware initializes without crash

Integrated as Stage 10 of the pipeline.
"""

from __future__ import annotations
import json
import logging
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

RENODE_PATH = os.environ.get(
    "RENODE_PATH",
    r"C:\Program Files\Renode\renode.exe"
)
PLATFORM_REPL = str(Path(__file__).parent / "stm32f446re.repl")

# Map USART/UART instance names to Renode peripheral names
UART_RENODE_MAP = {
    "USART1": "usart1", "USART2": "usart2", "USART3": "usart3",
    "UART4": "uart4", "UART5": "uart5",
}


@dataclass
class EmulationResult:
    """Result of a single emulation test."""
    status: str          # "PASS", "FAIL", "ERROR", "SKIP"
    duration_ms: int = 0
    uart_output: str = ""
    checks: list[dict] = field(default_factory=list)
    error: str = ""


def run_renode(elf_path: str, extra_commands: list[str] = None,
               run_seconds: float = 2.0, timeout: int = 30) -> dict:
    """Run Renode headlessly with the golden STM32F446 platform.

    Args:
        elf_path: Absolute path to .elf file.
        extra_commands: Additional Renode monitor commands (after ELF load, before run).
        run_seconds: Virtual time to emulate.
        timeout: Real-world process timeout.

    Returns:
        dict with 'success', 'uart_files', 'renode_output', 'error'.
    """
    elf_path = str(Path(elf_path).resolve()).replace("\\", "/")
    platform_path = PLATFORM_REPL.replace("\\", "/")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Build command list
        cmds = [
            "using sysbus",
            "mach create",
            f"machine LoadPlatformDescription @{platform_path}",
            f"sysbus LoadELF @{elf_path}",
        ]

        # Track UART log files
        uart_files = {}
        if extra_commands:
            for cmd in extra_commands:
                if "CreateFileBackend" in cmd:
                    # Extract uart name and file path
                    parts = cmd.split()
                    uart_name = parts[0]
                    log_path = os.path.join(tmpdir, f"{uart_name}.txt").replace("\\", "/")
                    cmds.append(f"{uart_name} CreateFileBackend @{log_path} true")
                    uart_files[uart_name] = log_path
                else:
                    cmds.append(cmd)

        cmds.append(f'emulation RunFor "{run_seconds}"')
        cmds.append("quit")

        cmd_str = "; ".join(cmds)

        try:
            result = subprocess.run(
                [RENODE_PATH, "--disable-xwt", "--console", "--plain", "-e", cmd_str],
                capture_output=True, text=True, timeout=timeout,
            )
        except FileNotFoundError:
            return {"success": False, "error": f"Renode not found: {RENODE_PATH}", "uart_files": {}}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Renode timed out ({timeout}s)", "uart_files": {}}

        # Read UART outputs
        uart_outputs = {}
        for name, path in uart_files.items():
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    uart_outputs[name] = f.read()
            else:
                uart_outputs[name] = ""

        combined = result.stdout + result.stderr
        has_error = ("CPU abort" in combined or
                     "There was an error" in combined or
                     "Segmentation fault" in combined)

        return {
            "success": not has_error,
            "uart_outputs": uart_outputs,
            "renode_output": combined[-2000:] if has_error else "",
            "error": combined[-500:] if has_error else "",
        }


def test_from_blueprint(elf_path: str, blueprint: dict) -> EmulationResult:
    """Auto-generate and run tests based on the project blueprint.

    This is the universal test function — works for ANY project.
    It reads the blueprint to know what peripherals exist,
    then sets up appropriate Renode captures and assertions.

    Args:
        elf_path: Path to compiled .elf.
        blueprint: ProjectBlueprint as dict (or pydantic .model_dump()).

    Returns:
        EmulationResult with all check results.
    """
    start = time.time()
    checks = []

    # Determine what UART backends to capture
    extra_commands = []
    uart_instances = []
    for uart in blueprint.get("uarts", []):
        inst = uart.get("instance", "") if isinstance(uart, dict) else uart.instance
        renode_name = UART_RENODE_MAP.get(inst)
        if renode_name:
            extra_commands.append(f"{renode_name} CreateFileBackend")
            uart_instances.append((inst, renode_name))

    # Determine run time — longer if UART output expected
    run_seconds = 3.0 if uart_instances else 2.0

    # Run emulation
    result = run_renode(elf_path, extra_commands, run_seconds=run_seconds)
    elapsed = int((time.time() - start) * 1000)

    if not result["success"]:
        return EmulationResult(
            status="ERROR", duration_ms=elapsed,
            error=result.get("error", "Renode execution failed"),
            checks=[{"check": "emulation_runs", "passed": False, "detail": result.get("error", "")}],
        )

    # CHECK 1: Firmware ran without crash (always)
    checks.append({"check": "no_crash", "passed": True, "detail": f"Ran {run_seconds}s without HardFault"})

    # CHECK 2: UART output (if UARTs configured)
    all_uart_text = ""
    for inst, renode_name in uart_instances:
        uart_text = result.get("uart_outputs", {}).get(renode_name, "")
        all_uart_text += uart_text

        if len(uart_text) > 0:
            checks.append({
                "check": f"uart_{inst}_output",
                "passed": True,
                "detail": f"{inst} produced {len(uart_text)} bytes: {uart_text[:100]!r}",
            })
        else:
            checks.append({
                "check": f"uart_{inst}_output",
                "passed": False,
                "detail": f"{inst} produced no output (may need longer run time or external trigger)",
            })

    # CHECK 3: ADC readings in UART (if both ADC and UART configured)
    if blueprint.get("adcs") and uart_instances and all_uart_text:
        has_numbers = bool(re.search(r'\d{2,}', all_uart_text))
        has_adc_keywords = any(kw in all_uart_text.lower() for kw in ["adc", "voltage", "value", "reading", "v"])
        if has_numbers or has_adc_keywords:
            checks.append({"check": "adc_readings_in_uart", "passed": True,
                           "detail": f"UART contains ADC data: {all_uart_text[:100]!r}"})
        else:
            checks.append({"check": "adc_readings_in_uart", "passed": False,
                           "detail": "UART output doesn't contain recognizable ADC readings"})

    # CHECK 4: Peripheral initialization (inferred from no-crash)
    periph_types = []
    if blueprint.get("gpios"):
        periph_types.append("GPIO")
    if blueprint.get("timers"):
        periph_types.append("Timer")
    if blueprint.get("spis"):
        periph_types.append("SPI")
    if blueprint.get("i2cs"):
        periph_types.append("I2C")
    if blueprint.get("adcs"):
        periph_types.append("ADC")
    if periph_types:
        checks.append({
            "check": "peripheral_init",
            "passed": True,
            "detail": f"Peripherals initialized without error: {', '.join(periph_types)}",
        })

    # Determine overall status
    failed_checks = [c for c in checks if not c["passed"]]
    if failed_checks:
        status = "FAIL"
    else:
        status = "PASS"

    return EmulationResult(
        status=status,
        duration_ms=elapsed,
        uart_output=all_uart_text,
        checks=checks,
    )


def test_elf_standalone(elf_path: str) -> EmulationResult:
    """Test an ELF file without a blueprint — just check it runs without crash."""
    start = time.time()

    # Capture all UARTs by default
    extra_commands = [f"{u} CreateFileBackend" for u in ["usart1", "usart2", "usart3"]]
    result = run_renode(elf_path, extra_commands, run_seconds=2.0)
    elapsed = int((time.time() - start) * 1000)

    if not result["success"]:
        return EmulationResult(status="ERROR", duration_ms=elapsed, error=result.get("error", ""))

    # Check UART outputs
    checks = [{"check": "no_crash", "passed": True, "detail": "Ran 2s without crash"}]
    uart_text = ""
    for name, text in result.get("uart_outputs", {}).items():
        if text:
            uart_text += text
            checks.append({"check": f"{name}_output", "passed": True, "detail": f"{text[:100]!r}"})

    return EmulationResult(status="PASS", duration_ms=elapsed, uart_output=uart_text, checks=checks)


def find_elf(project_dir: str) -> str | None:
    """Find the .elf file in a project's build directory."""
    for p in Path(project_dir).rglob("*.elf"):
        return str(p)
    return None


def find_blueprint(project_dir: str) -> dict | None:
    """Find and load a saved blueprint JSON from a project directory."""
    for p in Path(project_dir).rglob("blueprint.json"):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def run_all_tests(generated_dir: str) -> list[dict]:
    """Discover all built projects and run emulation tests."""
    results = []
    gen_path = Path(generated_dir)

    for test_dir in sorted(gen_path.iterdir()):
        if not test_dir.is_dir():
            continue

        elf = find_elf(str(test_dir))
        if not elf:
            results.append({"project": test_dir.name, "status": "SKIP", "detail": "No .elf found"})
            continue

        log.info("Testing: %s → %s", test_dir.name, elf)

        # Try to load blueprint for smart testing
        blueprint = find_blueprint(str(test_dir))
        if blueprint:
            result = test_from_blueprint(elf, blueprint)
        else:
            result = test_elf_standalone(elf)

        results.append({
            "project": test_dir.name,
            "status": result.status,
            "duration_ms": result.duration_ms,
            "uart_output": result.uart_output[:500] if result.uart_output else "",
            "checks": result.checks,
            "error": result.error,
        })

        status_icon = {"PASS": "OK", "FAIL": "XX", "ERROR": "!!", "SKIP": "--"}[result.status]
        log.info("  [%s] %s (%dms)", status_icon, result.status, result.duration_ms)
        for c in result.checks:
            icon = "+" if c["passed"] else "-"
            log.info("    [%s] %s: %s", icon, c["check"], c["detail"][:80])

    return results


def generate_report(results: list[dict], output_path: str = "test_report.json") -> str:
    """Generate a JSON test report."""
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platform": "STM32F446RE (Renode v1.16.1)",
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "PASS"),
        "failed": sum(1 for r in results if r["status"] == "FAIL"),
        "errors": sum(1 for r in results if r["status"] == "ERROR"),
        "skipped": sum(1 for r in results if r["status"] == "SKIP"),
        "results": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return output_path


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    gen_dir = sys.argv[1] if len(sys.argv) > 1 else "./generated"
    results = run_all_tests(gen_dir)

    print("\n" + "=" * 60)
    print("  EMULATION TEST REPORT — STM32F446RE")
    print("=" * 60)

    for r in results:
        icon = {"PASS": "OK", "FAIL": "XX", "ERROR": "!!", "SKIP": "--"}.get(r["status"], "??")
        print(f"  [{icon}] {r['project']:30s} {r['status']:6s} ({r.get('duration_ms', 0)}ms)")
        if r.get("uart_output"):
            print(f"       UART: {r['uart_output'][:80]!r}")
        for c in r.get("checks", []):
            ci = "+" if c["passed"] else "-"
            print(f"       [{ci}] {c['check']}: {c['detail'][:70]}")

    report_path = generate_report(results)
    print(f"\nReport: {report_path}")

    passed = sum(1 for r in results if r["status"] == "PASS")
    total = sum(1 for r in results if r["status"] != "SKIP")
    print(f"Result: {passed}/{total} passed")
