"""Build Agent — compiles the project and fixes errors."""

from __future__ import annotations
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from agents.agent_base import DeepSeekClient
from agents.failure_log import FailureLog

log = logging.getLogger(__name__)


@dataclass
class CompileError:
    file: str
    line: int
    column: int
    severity: str   # "error" or "warning"
    message: str


@dataclass
class BuildResult:
    success: bool
    elf_path: str = ""
    flash_size: int = 0
    ram_size: int = 0
    errors: list[CompileError] | None = None
    error_message: str = ""


# GCC error regex: file.c:42:5: error: message
GCC_ERROR_RE = re.compile(
    r"^(.+?):(\d+):(\d+):\s+(error|warning):\s+(.+)$",
    re.MULTILINE,
)

# Size output regex
SIZE_RE = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)", re.MULTILINE)


class BuildAgent:
    """Compiles the project and attempts to fix errors with LLM assistance."""

    def __init__(self, client: DeepSeekClient, max_attempts: int = 3):
        self.client = client
        self.max_attempts = max_attempts
        self.failure_log = FailureLog("build")
        self.codegen_log = FailureLog("codegen")

    def build(self, project_dir: Path) -> BuildResult:
        """Run make and return the result."""
        try:
            result = subprocess.run(
                ["make", "-C", str(project_dir), "-j4"],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except FileNotFoundError:
            return BuildResult(
                success=False,
                error_message="'make' not found. Install build-essential or use Docker.",
            )
        except subprocess.TimeoutExpired:
            return BuildResult(success=False, error_message="Build timed out (120s)")

        if result.returncode == 0:
            # Parse size output
            flash, ram = self._parse_size(result.stdout + result.stderr)
            elf = self._find_elf(project_dir)
            return BuildResult(
                success=True,
                elf_path=str(elf) if elf else "",
                flash_size=flash,
                ram_size=ram,
            )

        # Parse errors
        errors = self._parse_errors(result.stderr + result.stdout)
        return BuildResult(
            success=False,
            errors=errors,
            error_message=result.stderr[-2000:] if result.stderr else result.stdout[-2000:],
        )

    def build_with_fix_loop(self, project_dir: Path) -> BuildResult:
        """Build with automatic error fixing loop.

        Strategy: send the ENTIRE file + ALL errors to DeepSeek in one call,
        get back the complete corrected file. No blind line splicing.
        """
        for attempt in range(self.max_attempts):
            log.info("Build attempt %d/%d", attempt + 1, self.max_attempts)

            # Clean before retry (except first attempt)
            if attempt > 0:
                subprocess.run(
                    ["make", "-C", str(project_dir), "clean"],
                    capture_output=True, timeout=30,
                )

            result = self.build(project_dir)
            if result.success:
                log.info("Build succeeded on attempt %d", attempt + 1)
                return result

            if not result.errors:
                log.error("Build failed with no parseable errors: %s", result.error_message[:500])
                return result

            # Record errors for learning (on first attempt only — before fixes corrupt things)
            if attempt == 0:
                for err in result.errors:
                    # Record to codegen log (most errors come from LLM-generated code)
                    if "main.c" in err.file:
                        self.codegen_log.record_compile_error(err.file, err.line, err.message)
                    self.failure_log.record_compile_error(err.file, err.line, err.message)

            # Group errors by file
            errors_by_file: dict[str, list[CompileError]] = {}
            for err in result.errors:
                errors_by_file.setdefault(err.file, []).append(err)

            # Fix all files with errors in one pass
            any_fixed = False
            for file_rel, file_errors in errors_by_file.items():
                fixed = self._try_fix_file(project_dir, file_rel, file_errors)
                if fixed:
                    any_fixed = True

            if not any_fixed:
                log.warning("Could not fix any errors")
                return result

        log.error("Build failed after %d attempts", self.max_attempts)
        return result

    def _try_fix_file(self, project_dir: Path, file_rel: str, errors: list[CompileError]) -> bool:
        """Fix ALL errors in a single file by sending the whole file to DeepSeek."""
        file_path = project_dir / file_rel
        if not file_path.is_file():
            return False

        source = file_path.read_text(encoding="utf-8", errors="replace")

        # Format all errors for this file
        error_list = "\n".join(
            f"  Line {e.line}: {e.severity}: {e.message}" for e in errors
        )

        system = (
            "You are fixing GCC compiler errors in an STM32 project.\n"
            "You will receive the COMPLETE source file and ALL errors.\n"
            "Return the COMPLETE corrected file — every line, top to bottom.\n"
            "Do NOT add explanations, comments about changes, or markdown fences.\n"
            "Do NOT remove existing functions or restructure the code.\n"
            "Only fix the specific errors listed. Preserve all working code exactly.\n"
            "Return ONLY the corrected C source code."
        )
        user = (
            f"File: {file_rel}\n"
            f"Errors ({len(errors)} total):\n{error_list}\n\n"
            f"Complete source:\n{source}"
        )

        try:
            resp = self.client.reason(system, user, max_tokens=8192)
            fixed_source = resp.content.strip()

            # Strip markdown fences if DeepSeek wrapped the output
            if fixed_source.startswith("```"):
                lines = fixed_source.split("\n")
                if lines[-1].strip() == "```":
                    lines = lines[1:-1]
                elif lines[0].startswith("```"):
                    lines = lines[1:]
                fixed_source = "\n".join(lines)

            # Sanity check: corrected file should be similar size (not empty or truncated)
            orig_lines = len(source.split("\n"))
            fixed_lines = len(fixed_source.split("\n"))
            if fixed_lines < orig_lines * 0.5:
                log.warning("Fix rejected: output too short (%d lines vs original %d)",
                            fixed_lines, orig_lines)
                return False

            file_path.write_text(fixed_source, encoding="utf-8")
            log.info("Applied fix to %s (%d errors, %d→%d lines)",
                     file_rel, len(errors), orig_lines, fixed_lines)
            return True

        except Exception as e:
            log.error("Fix attempt failed: %s", e)
            return False

    def _parse_errors(self, output: str) -> list[CompileError]:
        """Parse GCC error output into structured errors."""
        errors = []
        for match in GCC_ERROR_RE.finditer(output):
            errors.append(CompileError(
                file=match.group(1),
                line=int(match.group(2)),
                column=int(match.group(3)),
                severity=match.group(4),
                message=match.group(5),
            ))
        return errors

    def _parse_size(self, output: str) -> tuple[int, int]:
        """Parse arm-none-eabi-size output for text and data sizes."""
        match = SIZE_RE.search(output)
        if match:
            text = int(match.group(1))
            data = int(match.group(2))
            bss = int(match.group(3))
            return text + data, data + bss  # flash, ram
        return 0, 0

    def _find_elf(self, project_dir: Path) -> Path | None:
        """Find the .elf file in the build directory."""
        build_dir = project_dir / "build"
        if build_dir.is_dir():
            for f in build_dir.iterdir():
                if f.suffix == ".elf":
                    return f
        return None
