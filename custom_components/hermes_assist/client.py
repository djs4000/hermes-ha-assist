from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import aiohttp

_LOGGER = logging.getLogger(__name__)


class HermesAssistError(Exception):
    """Base Hermes Assist client error."""


class HermesAuthError(HermesAssistError):
    """Hermes API authentication failed."""


class HermesTimeoutError(HermesAssistError):
    """Hermes did not respond before the configured deadline."""


@dataclass(frozen=True)
class HermesAssistResponse:
    speech: str
    raw: dict[str, Any]


def normalize_chat_completions_url(api_url: str) -> str:
    """Accept a Hermes host/base/v1 URL and return /v1/chat/completions."""
    url = (api_url or "").strip().rstrip("/")
    if not url:
        raise ValueError("Hermes API URL is required")
    if url.endswith("/v1/chat/completions"):
        return url
    if url.endswith("/v1"):
        return f"{url}/chat/completions"
    return urljoin(f"{url}/", "v1/chat/completions")


class HermesAssistClient:
    """Small async client for Hermes' OpenAI-compatible chat completions API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        api_url: str,
        api_token: str,
        model: str,
        timeout: float,
        system_prompt: str,
    ) -> None:
        self._session = session
        self.api_url = normalize_chat_completions_url(api_url)
        self._api_token = api_token
        self._model = model
        self._timeout = aiohttp.ClientTimeout(total=float(timeout))
        self._system_prompt = system_prompt

    async def async_validate(self) -> None:
        """Send a small request to validate URL/token/model."""
        await self.async_ask(
            "Reply with exactly: ok",
            conversation_id="home-assistant-config-flow",
            language="en",
        )

    async def async_ask(
        self,
        text: str,
        *,
        conversation_id: str | None,
        language: str | None,
        device_name: str | None = None,
    ) -> HermesAssistResponse:
        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
        }
        session_key = _session_key(conversation_id)
        if session_key:
            headers["X-Hermes-Session-Key"] = session_key
            headers["X-Hermes-Session-Id"] = session_key

        user_message = _format_user_message(text, language=language, device_name=device_name)
        payload: dict[str, Any] = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_message},
            ],
        }

        try:
            async with self._session.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            ) as response:
                raw_text = await response.text()
                if response.status in {401, 403}:
                    raise HermesAuthError("Hermes API rejected the configured token")
                if response.status >= 400:
                    raise HermesAssistError(
                        f"Hermes API returned HTTP {response.status}: {raw_text[:500]}"
                    )
                try:
                    data = await response.json()
                except Exception as exc:  # pragma: no cover - defensive
                    raise HermesAssistError("Hermes API returned non-JSON response") from exc
        except TimeoutError as exc:
            raise HermesTimeoutError("Hermes did not respond before the voice deadline") from exc
        except asyncio.TimeoutError as exc:
            raise HermesTimeoutError("Hermes did not respond before the voice deadline") from exc
        except aiohttp.ClientError as exc:
            raise HermesAssistError(f"Could not connect to Hermes API: {exc}") from exc

        speech = extract_speech(data)
        if not speech:
            raise HermesAssistError("Hermes returned an empty response")
        return HermesAssistResponse(speech=speech, raw=data)


def extract_speech(data: dict[str, Any]) -> str:
    """Extract assistant speech from OpenAI-compatible chat completions data."""
    try:
        choices = data.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    if isinstance(item.get("text"), str):
                        parts.append(item["text"])
                    elif isinstance(item.get("content"), str):
                        parts.append(item["content"])
            return "".join(parts).strip()
    except Exception:
        _LOGGER.debug("Failed to extract Hermes speech", exc_info=True)
    return ""


def _format_user_message(text: str, *, language: str | None, device_name: str | None) -> str:
    lines = ["Home Assistant Assist voice request."]
    if language:
        lines.append(f"Language: {language}")
    if device_name:
        lines.append(f"Device: {device_name}")
    lines.append(f"User request: {text}")
    return "\n".join(lines)


def _session_key(conversation_id: str | None) -> str | None:
    if not conversation_id:
        return None
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", ":"} else "_" for ch in conversation_id)
    return f"ha-assist:{safe[:200]}"
