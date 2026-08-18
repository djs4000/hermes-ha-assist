from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

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


@dataclass(frozen=True)
class HermesRunStart:
    run_id: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class HermesRunStatus:
    run_id: str
    status: str
    output: str
    raw: dict[str, Any]

    @property
    def is_terminal(self) -> bool:
        return self.status in {"completed", "failed", "cancelled"}


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


def normalize_runs_url(api_url: str) -> str:
    """Accept a Hermes host/base/chat URL and return /v1/runs."""
    chat_url = normalize_chat_completions_url(api_url)
    suffix = "/v1/chat/completions"
    if not chat_url.endswith(suffix):
        raise ValueError("Hermes chat completions URL must end with /v1/chat/completions")
    return f"{chat_url[: -len(suffix)]}/v1/runs"


def build_chat_completions_url(api_host: str, api_port: int | str) -> str:
    """Build the documented Hermes chat completions endpoint from host + port."""
    host = (api_host or "").strip().rstrip("/")
    if not host:
        raise ValueError("Hermes URL is required")
    port = str(api_port).strip()
    if not port:
        raise ValueError("Hermes API port is required")

    parts = urlsplit(host)
    if not parts.scheme or not parts.netloc:
        raise ValueError("Hermes URL must include http:// or https://")

    hostname = parts.hostname or parts.netloc
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    if parts.username:
        auth = parts.username
        if parts.password:
            auth = f"{auth}:{parts.password}"
        netloc = f"{auth}@{netloc}"
    netloc = f"{netloc}:{port}"
    base = urlunsplit((parts.scheme, netloc, parts.path.rstrip("/"), "", ""))
    return normalize_chat_completions_url(base)


class HermesAssistClient:
    """Small async client for Hermes' OpenAI-compatible API."""

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
        self.runs_url = normalize_runs_url(self.api_url)
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
        headers = self._headers(conversation_id)
        user_message = _format_user_message(text, language=language, device_name=device_name)
        payload: dict[str, Any] = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_message},
            ],
        }

        data = await self._post_json(self.api_url, headers=headers, payload=payload)
        speech = extract_speech(data)
        if not speech:
            raise HermesAssistError("Hermes returned an empty response")
        return HermesAssistResponse(speech=speech, raw=data)

    async def async_start_run(
        self,
        text: str,
        *,
        conversation_id: str | None,
        language: str | None,
        device_name: str | None = None,
    ) -> HermesRunStart:
        """Start a long-running Hermes run and return its run id."""
        headers = self._headers(conversation_id)
        session_key = _session_key(conversation_id)
        user_message = _format_user_message(text, language=language, device_name=device_name)
        payload: dict[str, Any] = {
            "model": self._model,
            "input": user_message,
            "instructions": self._system_prompt,
        }
        if session_key:
            payload["session_id"] = session_key

        data = await self._post_json(self.runs_url, headers=headers, payload=payload)
        run_id = str(data.get("run_id") or "")
        if not run_id:
            raise HermesAssistError("Hermes run response did not include a run_id")
        return HermesRunStart(run_id=run_id, raw=data)

    async def async_get_run(self, run_id: str) -> HermesRunStatus:
        """Return the current status for a Hermes run."""
        data = await self._get_json(f"{self.runs_url}/{run_id}", headers=self._headers(None))
        status = str(data.get("status") or "")
        output = str(data.get("output") or data.get("error") or "")
        return HermesRunStatus(run_id=run_id, status=status, output=output, raw=data)

    async def _post_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            async with self._session.post(
                url,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            ) as response:
                return await _json_or_error(response)
        except TimeoutError as exc:
            raise HermesTimeoutError("Hermes did not respond before the voice deadline") from exc
        except aiohttp.ClientError as exc:
            raise HermesAssistError(f"Could not connect to Hermes API: {exc}") from exc

    async def _get_json(self, url: str, *, headers: dict[str, str]) -> dict[str, Any]:
        try:
            async with self._session.get(url, headers=headers, timeout=self._timeout) as response:
                return await _json_or_error(response)
        except TimeoutError as exc:
            raise HermesTimeoutError("Hermes did not respond before the voice deadline") from exc
        except aiohttp.ClientError as exc:
            raise HermesAssistError(f"Could not connect to Hermes API: {exc}") from exc

    def _headers(self, conversation_id: str | None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
        }
        session_key = _session_key(conversation_id)
        if session_key:
            headers["X-Hermes-Session-Key"] = session_key
            headers["X-Hermes-Session-Id"] = session_key
        return headers


async def _json_or_error(response: aiohttp.ClientResponse) -> dict[str, Any]:
    raw_text = await response.text()
    if response.status in {401, 403}:
        raise HermesAuthError("Hermes API rejected the configured token")
    if response.status >= 400:
        raise HermesAssistError(f"Hermes API returned HTTP {response.status}: {raw_text[:500]}")
    try:
        data = await response.json()
    except Exception as exc:  # pragma: no cover - defensive
        raise HermesAssistError("Hermes API returned non-JSON response") from exc
    if not isinstance(data, dict):
        raise HermesAssistError("Hermes API returned unexpected JSON")
    return data


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
