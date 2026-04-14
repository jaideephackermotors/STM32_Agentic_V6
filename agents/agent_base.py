"""DeepSeek V3.2 Reasoner client — native HTTP, zero OpenAI dependency."""

from __future__ import annotations
import json
import logging
import os
import time
from dataclasses import dataclass

import requests

log = logging.getLogger(__name__)


@dataclass
class ReasonerResponse:
    """Response from DeepSeek Reasoner."""
    reasoning: str    # Chain-of-thought reasoning (thinking tokens)
    content: str      # Final answer
    model: str = ""
    usage_tokens: int = 0


class DeepSeekClient:
    """Thin wrapper around DeepSeek's chat/completions API.

    Uses deepseek-reasoner (V3.2 thinking mode) for all calls.
    No OpenAI package dependency — just requests.
    """

    BASE_URL = "https://api.deepseek.com"

    def __init__(self, api_key: str | None = None, model: str = "deepseek-reasoner"):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY not set. Pass it directly or set the environment variable."
            )
        self.model = model
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def reason(
        self,
        system: str,
        user: str,
        max_tokens: int = 8192,
        temperature: float = 0.0,
    ) -> ReasonerResponse:
        """Send a reasoning request to DeepSeek.

        Args:
            system: System prompt defining the agent's role and constraints.
            user: User message (requirements, code context, etc.).
            max_tokens: Max output tokens.
            temperature: Sampling temperature (0.0 = deterministic).

        Returns:
            ReasonerResponse with reasoning chain and final content.
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        log.info("DeepSeek request: model=%s, system_len=%d, user_len=%d",
                 self.model, len(system), len(user))

        start = time.time()
        resp = self.session.post(
            f"{self.BASE_URL}/chat/completions",
            json=payload,
            timeout=300,  # 5 min timeout for reasoning
        )
        elapsed = time.time() - start

        if resp.status_code != 200:
            log.error("DeepSeek API error %d: %s", resp.status_code, resp.text)
            raise RuntimeError(f"DeepSeek API error {resp.status_code}: {resp.text}")

        data = resp.json()
        choice = data["choices"][0]
        msg = choice["message"]
        usage = data.get("usage", {})

        result = ReasonerResponse(
            reasoning=msg.get("reasoning_content", ""),
            content=msg.get("content", ""),
            model=data.get("model", self.model),
            usage_tokens=usage.get("total_tokens", 0),
        )

        log.info("DeepSeek response: %.1fs, %d tokens", elapsed, result.usage_tokens)
        return result

    def reason_json(
        self,
        system: str,
        user: str,
        max_tokens: int = 8192,
        json_schema: dict | None = None,
    ) -> dict:
        """Call reason() and parse the content as JSON.

        If json_schema is provided, attempts schema-constrained decoding first.
        Falls back to standard JSON parsing if the API doesn't support it.
        Strips markdown code fences if present.
        Raises ValueError if content is not valid JSON.
        """
        # Build payload — try json_schema enforcement first
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.0,
            "stream": False,
        }

        if json_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": json_schema,
            }

        log.info("DeepSeek request: model=%s, system_len=%d, user_len=%d, schema=%s",
                 self.model, len(system), len(user), "yes" if json_schema else "no")

        start = time.time()
        resp = self.session.post(
            f"{self.BASE_URL}/chat/completions",
            json=payload,
            timeout=300,
        )
        elapsed = time.time() - start

        # If schema enforcement failed (API doesn't support it), retry without
        if resp.status_code in (400, 422) and json_schema:
            log.warning("json_schema not supported by API, falling back to plain JSON")
            payload.pop("response_format", None)
            start = time.time()
            resp = self.session.post(
                f"{self.BASE_URL}/chat/completions",
                json=payload,
                timeout=300,
            )
            elapsed = time.time() - start

        if resp.status_code != 200:
            log.error("DeepSeek API error %d: %s", resp.status_code, resp.text)
            raise RuntimeError(f"DeepSeek API error {resp.status_code}: {resp.text}")

        data = resp.json()
        choice = data["choices"][0]
        msg = choice["message"]
        usage = data.get("usage", {})

        log.info("DeepSeek response: %.1fs, %d tokens",
                 elapsed, usage.get("total_tokens", 0))

        content = msg.get("content", "").strip()

        # Strip ```json ... ``` fences
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            elif lines[0].startswith("```"):
                lines = lines[1:]
            content = "\n".join(lines)

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            log.error("Failed to parse DeepSeek JSON response: %s\nContent: %s", e, content[:500])
            raise ValueError(f"DeepSeek returned invalid JSON: {e}") from e

    def reason_json_validated(
        self,
        system: str,
        user: str,
        model_class,
        normalize_fn=None,
        max_tokens: int = 8192,
    ) -> dict:
        """Call reason_json() with pydantic validation retry (Option 1 fallback).

        1. Get JSON from DeepSeek (with schema enforcement if supported)
        2. Run optional normalize_fn on the data
        3. Validate with model_class (pydantic)
        4. If validation fails, send the error + schema back to DeepSeek for one retry
        """
        # Try with schema enforcement
        schema = model_class.model_json_schema()
        data = self.reason_json(system, user, max_tokens=max_tokens, json_schema=schema)

        # Normalize if provided
        if normalize_fn:
            normalize_fn(data)

        # First validation attempt
        validation_error_str = ""
        try:
            model_class(**data)
            return data
        except Exception as e:
            validation_error_str = str(e)
            log.warning("Validation failed, retrying with error feedback: %s",
                        validation_error_str[:300])

            # Record failure for future prompt enrichment
            try:
                from agents.failure_log import FailureLog
                FailureLog("architect").record_validation_error(validation_error_str, data)
            except Exception:
                pass  # Don't let logging break the pipeline

        # Retry: send the error + original JSON back
        retry_system = (
            "The JSON you produced has validation errors. Fix them.\n"
            "Return ONLY the corrected JSON, no explanation, no markdown.\n"
        )
        retry_user = (
            f"Validation errors:\n{validation_error_str}\n\n"
            f"Required schema:\n{json.dumps(schema, indent=2)[:3000]}\n\n"
            f"Your original JSON:\n{json.dumps(data, indent=2)}"
        )
        data = self.reason_json(retry_system, retry_user, max_tokens=max_tokens)

        if normalize_fn:
            normalize_fn(data)

        return data
