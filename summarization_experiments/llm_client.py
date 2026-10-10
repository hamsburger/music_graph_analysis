"""Thin OpenRouter chat-completions client.

Mirrors the shape of :class:`music_graph_analysis.genius.GeniusClient`: all
network access goes through :meth:`OpenRouterClient.complete`, with a timeout,
retries and exponential backoff on transient failures, and an optional
client-side throttle. The API key is read from ``OPENROUTER_API_KEY``.
"""

from __future__ import annotations

import time
from typing import Any

import requests

from .config import OPENROUTER_BASE_URL, openrouter_api_key


class LLMError(RuntimeError):
    """Raised when an LLM request cannot be completed."""


class OpenRouterClient:
    """Minimal OpenRouter client using the OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = OPENROUTER_BASE_URL,
        timeout: float = 120.0,
        *,
        max_retries: int = 3,
        backoff: float = 1.0,
        min_interval: float = 0.0,
    ) -> None:
        key = api_key or openrouter_api_key()
        if not key:
            raise LLMError(
                "No OpenRouter API key provided. Set OPENROUTER_API_KEY "
                "or pass api_key=..."
            )
        self.api_key = key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self.backoff = backoff
        self.min_interval = min_interval
        self._last_request_at: float | None = None

    def _throttle(self) -> None:
        if self.min_interval <= 0 or self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.min_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def complete(
        self,
        prompt: str,
        *,
        model: str,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """Return the assistant's text for ``prompt`` using ``model``."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                response = requests.post(
                    url, headers=headers, json=payload, timeout=self.timeout
                )
            except requests.RequestException as exc:
                last_error = exc
            else:
                self._last_request_at = time.monotonic()

                if response.status_code == 200:
                    try:
                        body = response.json()
                        return body["choices"][0]["message"]["content"]
                    except (ValueError, KeyError, IndexError, TypeError) as exc:
                        raise LLMError(
                            f"OpenRouter returned an unexpected response: {exc}"
                        ) from exc

                if response.status_code == 429 or response.status_code >= 500:
                    last_error = LLMError(
                        f"OpenRouter error {response.status_code} for {model}"
                    )
                else:
                    raise LLMError(
                        f"OpenRouter error {response.status_code} for {model}: "
                        f"{response.text[:500]}"
                    )

            if attempt < self.max_retries - 1:
                time.sleep(self.backoff * (2**attempt))

        raise LLMError(
            f"OpenRouter request failed for {model} after "
            f"{self.max_retries} attempts: {last_error}"
        ) from last_error
