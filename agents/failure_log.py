"""Failure log — records and retrieves failures for prompt enrichment.

Supports multiple stages, each with its own log file:
  - architect: schema validation errors (field names, types, enums)
  - parser: requirement parsing errors
  - codegen: compile errors from LLM-generated application code
  - build: recurring build errors and fixes
"""

from __future__ import annotations
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

LOG_DIR = Path(__file__).parent.parent / "failure_logs"


class FailureLog:
    """Append-only log of LLM failures for a specific pipeline stage.

    Each entry records what went wrong and what the fix was.
    Used to inject "mistakes to avoid" into future prompts.
    """

    def __init__(self, stage: str = "architect"):
        self.stage = stage
        LOG_DIR.mkdir(exist_ok=True)
        self.path = LOG_DIR / f"{stage}.jsonl"

    def record(self, entry: dict) -> None:
        """Append a failure entry. Deduplicates by (category, wrong) key."""
        existing = self._load()

        # Deduplicate
        cat = entry.get("category", entry.get("field", ""))
        wrong = str(entry.get("wrong", entry.get("error", "")))
        for e in existing:
            e_cat = e.get("category", e.get("field", ""))
            e_wrong = str(e.get("wrong", e.get("error", "")))
            if e_cat == cat and e_wrong == wrong:
                return  # Already recorded

        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        log.info("Recorded %s failure: %s", self.stage, entry)

    def record_validation_error(self, error_str: str, raw_data: dict = None) -> None:
        """Parse a pydantic ValidationError string and record structured entries."""
        import re
        pattern = r"(\w[\w.]+)\n\s+Input should be (.+?) \[type=\w+, input_value='?([^',\]]+)"
        for match in re.finditer(pattern, error_str):
            field = match.group(1)
            expected = match.group(2)
            got = match.group(3)
            self.record({"field": field, "wrong": got, "expected": expected})

        missing_pattern = r"(\w[\w.]+)\n\s+Field required"
        for match in re.finditer(missing_pattern, error_str):
            field = match.group(1)
            self.record({"field": field, "error": "missing", "note": "LLM used wrong field name"})

    def record_compile_error(self, file: str, line: int, message: str, fix_applied: str = "") -> None:
        """Record a compile error from the build stage."""
        self.record({
            "category": "compile",
            "file": file,
            "error": message,
            "fix": fix_applied,
        })

    def record_parse_error(self, error: str, raw_input: str = "") -> None:
        """Record a requirement parsing error."""
        self.record({
            "category": "parse",
            "error": error,
            "input_snippet": raw_input[:200] if raw_input else "",
        })

    def get_prompt_section(self, max_entries: int = 20) -> str:
        """Generate a prompt section from recorded failures.

        Returns empty string if no failures recorded.
        """
        entries = self._load()
        if not entries:
            return ""

        # Take most recent entries (newest mistakes are most relevant)
        entries = entries[-max_entries:]

        headers = {
            "architect": "COMMON SCHEMA MISTAKES TO AVOID (from past failures):",
            "parser": "COMMON PARSING MISTAKES TO AVOID (from past failures):",
            "codegen": "COMMON CODE MISTAKES TO AVOID (from past compile errors):",
            "build": "RECURRING BUILD ISSUES (from past failures):",
        }
        lines = [headers.get(self.stage, f"MISTAKES TO AVOID ({self.stage}):")]

        for e in entries:
            if "field" in e and "wrong" in e and "expected" in e:
                lines.append(f"  - {e['field']}: use {e['expected']}, NOT '{e['wrong']}'")
            elif "category" in e and e["category"] == "compile":
                error_msg = e.get("error", "")
                fix_msg = e.get("fix", "")
                if fix_msg:
                    lines.append(f"  - Compile error: {error_msg[:80]} → Fix: {fix_msg[:80]}")
                else:
                    lines.append(f"  - Avoid: {error_msg[:100]}")
            elif "category" in e and e["category"] == "parse":
                lines.append(f"  - Parse error: {e.get('error', '')[:100]}")
            elif "error" in e:
                lines.append(f"  - {e.get('field', '?')}: {e.get('note', e['error'])}")
            else:
                lines.append(f"  - {json.dumps(e)}")

        return "\n".join(lines) + "\n"

    def _load(self) -> list[dict]:
        """Load all entries from the log file."""
        if not self.path.is_file():
            return []
        entries = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return entries
