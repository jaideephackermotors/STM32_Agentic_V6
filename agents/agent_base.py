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
    ) -> dict:
        """Call reason() and parse the content as JSON.

        Strips markdown code fences if present.
        Raises ValueError if content is not valid JSON.
        """
        resp = self.reason(system, user, max_tokens=max_tokens)
        content = resp.content.strip()

        # Strip ```json ... ``` fences
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first line (```json) and last line (```)
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
