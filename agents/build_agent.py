"""Build Agent — compiles the project and fixes errors."""

from __future__ import annotations
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from agents.agent_base import DeepSeekClient

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

    def __init__(self, client: DeepSeekClient, max_attempts: int = 5):
        self.client = client
        self.max_attempts = max_attempts

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

        Attempts to fix compiler errors by:
        1. Parsing GCC error output
        2. Reading the offending source file
        3. Asking DeepSeek for a targeted fix
        4. Applying the fix
        5. Rebuilding (up to max_attempts)
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

            # Try to fix the first error
            fixed = self._try_fix(project_dir, result.errors[0])
            if not fixed:
                log.warning("Could not fix error: %s", result.errors[0].message)
                return result

        log.error("Build failed after %d attempts", self.max_attempts)
        return result

    def _try_fix(self, project_dir: Path, error: CompileError) -> bool:
        """Attempt to fix a single compiler error using LLM."""
        file_path = project_dir / error.file
        if not file_path.is_file():
            return False

        source = file_path.read_text(encoding="utf-8", errors="replace")

        # Get context around the error line
        lines = source.split("\n")
        start = max(0, error.line - 5)
        end = min(len(lines), error.line + 5)
        context = "\n".join(f"{i+1}: {lines[i]}" for i in range(start, end))

        system = (
            "You are fixing a GCC compiler error in an STM32 project.\n"
            "Return ONLY the corrected lines (no explanation, no markdown).\n"
            "Return the FULL corrected block from the context shown, preserving line numbers.\n"
            "Format: one line per source line, no line numbers in output."
        )
        user = (
            f"File: {error.file}\n"
            f"Error at line {error.line}: {error.message}\n\n"
            f"Context:\n{context}"
        )

        try:
            resp = self.client.reason(system, user, max_tokens=2048)
            fixed_block = resp.content.strip()

            # Replace the context region with the fix
            new_lines = list(lines)
            fix_lines = fixed_block.split("\n")
            # Replace lines start..end with fix
            new_lines[start:end] = fix_lines
            file_path.write_text("\n".join(new_lines), encoding="utf-8")
            log.info("Applied fix to %s:%d", error.file, error.line)
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
