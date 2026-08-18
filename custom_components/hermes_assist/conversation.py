from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import (
    HermesAssistClient,
    HermesAssistError,
    HermesRunStatus,
    build_chat_completions_url,
)
from .const import (
    CONF_API_HOST,
    CONF_API_PORT,
    CONF_API_TOKEN,
    CONF_API_URL,
    CONF_COMPLETION_ANNOUNCE_ENTITY,
    CONF_COMPLETION_MEDIA_PLAYER_ENTITY,
    CONF_COMPLETION_TTS_ENTITY,
    CONF_COMPLETION_TTS_LANGUAGE,
    CONF_COMPLETION_TTS_VOICE,
    CONF_HANDOFF_MODEL,
    CONF_HANDOFF_TIMEOUT,
    CONF_MODEL,
    CONF_SYSTEM_PROMPT,
    CONF_TIMEOUT,
    CONF_VOICE_WAIT_TIMEOUT,
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    DEFAULT_COMPLETION_ANNOUNCE_ENTITY,
    DEFAULT_COMPLETION_MEDIA_PLAYER_ENTITY,
    DEFAULT_COMPLETION_TTS_ENTITY,
    DEFAULT_COMPLETION_TTS_LANGUAGE,
    DEFAULT_COMPLETION_TTS_VOICE,
    DEFAULT_HANDOFF_MODEL,
    DEFAULT_HANDOFF_SPEECH,
    DEFAULT_HANDOFF_TIMEOUT,
    DEFAULT_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TIMEOUT,
    DEFAULT_VOICE_WAIT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
_HANDOFF_SPEECH = DEFAULT_HANDOFF_SPEECH
_UNAVAILABLE_SPEECH = "I’m sorry, Hermes is not available right now."
_TABLET_MESSAGE_MAX_CHARS = 420
_FOLLOWUP_QUESTION_MAX_CHARS = 320
_LONG_RESULT_TRIGGER_CHARS = 650
_FULL_REPORT_LOCATION = "Home Assistant notifications"
_RUN_POLL_INTERVAL = 1.0
_RUN_BACKGROUND_TIMEOUT = 300
_PENDING_FOLLOWUP_TTL_SECONDS = 300
_SHORT_REPLY_MAX_WORDS = 8


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up the Hermes conversation agent."""
    agent = HermesConversationAgent(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = agent
    conversation.async_set_agent(hass, entry, agent)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload Hermes Assist when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload the Hermes conversation agent."""
    conversation.async_unset_agent(hass, entry)
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)


class HermesConversationAgent(conversation.AbstractConversationAgent):
    """Home Assistant conversation agent backed by Hermes Agent."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._pending_followups: dict[str, dict[str, Any]] = {}
        data = entry.data
        api_url = _entry_api_url(data)
        self._voice_wait_timeout = float(
            entry.options.get(
                CONF_VOICE_WAIT_TIMEOUT,
                data.get(CONF_VOICE_WAIT_TIMEOUT, DEFAULT_VOICE_WAIT_TIMEOUT),
            )
        )
        self._handoff_model = entry.options.get(
            CONF_HANDOFF_MODEL,
            data.get(CONF_HANDOFF_MODEL, DEFAULT_HANDOFF_MODEL),
        ).strip()
        self._handoff_timeout = float(
            entry.options.get(
                CONF_HANDOFF_TIMEOUT,
                data.get(CONF_HANDOFF_TIMEOUT, DEFAULT_HANDOFF_TIMEOUT),
            )
        )
        self._completion_announce_entity = entry.options.get(
            CONF_COMPLETION_ANNOUNCE_ENTITY,
            data.get(CONF_COMPLETION_ANNOUNCE_ENTITY, DEFAULT_COMPLETION_ANNOUNCE_ENTITY),
        ).strip()
        self._completion_tts_entity = entry.options.get(
            CONF_COMPLETION_TTS_ENTITY,
            data.get(CONF_COMPLETION_TTS_ENTITY, DEFAULT_COMPLETION_TTS_ENTITY),
        ).strip()
        self._completion_media_player_entity = entry.options.get(
            CONF_COMPLETION_MEDIA_PLAYER_ENTITY,
            data.get(
                CONF_COMPLETION_MEDIA_PLAYER_ENTITY,
                DEFAULT_COMPLETION_MEDIA_PLAYER_ENTITY,
            ),
        ).strip()
        self._completion_tts_language = entry.options.get(
            CONF_COMPLETION_TTS_LANGUAGE,
            data.get(CONF_COMPLETION_TTS_LANGUAGE, DEFAULT_COMPLETION_TTS_LANGUAGE),
        ).strip()
        self._completion_tts_voice = entry.options.get(
            CONF_COMPLETION_TTS_VOICE,
            data.get(CONF_COMPLETION_TTS_VOICE, DEFAULT_COMPLETION_TTS_VOICE),
        ).strip()
        self._client = HermesAssistClient(
            async_get_clientsession(hass),
            api_url=api_url,
            api_token=data[CONF_API_TOKEN],
            model=entry.options.get(CONF_MODEL, data.get(CONF_MODEL, DEFAULT_MODEL)),
            timeout=entry.options.get(CONF_TIMEOUT, data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
            system_prompt=entry.options.get(
                CONF_SYSTEM_PROMPT, data.get(CONF_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT)
            ),
        )

    @property
    def supported_languages(self) -> list[str] | str:
        """Return supported languages."""
        return "*"

    async def async_process(
        self,
        user_input: conversation.ConversationInput,
    ) -> conversation.ConversationResult:
        """Process a sentence through Hermes."""
        conversation_id = getattr(user_input, "conversation_id", None)
        language = getattr(user_input, "language", None)
        device_id = getattr(user_input, "device_id", None)
        device_name = self._device_name(user_input)
        pending_followup = self._consume_pending_followup(user_input)
        request_text = (
            _followup_reply_prompt(user_input.text, pending_followup)
            if pending_followup
            else user_input.text
        )
        hermes_conversation_id = (
            pending_followup.get("conversation_id") if pending_followup else conversation_id
        )
        try:
            run = await self._client.async_start_run(
                request_text,
                conversation_id=hermes_conversation_id,
                language=language,
                device_name=device_name,
            )
            handoff_task = self._start_handoff_task(
                request_text,
                language=language,
                device_name=device_name,
            )
            status = await self._wait_for_run(run.run_id, self._voice_wait_timeout)
            if status and status.status == "completed" and status.output:
                _cancel_task(handoff_task)
                if await self._start_immediate_followup_conversation_if_needed(
                    status.output,
                    request_text=request_text,
                    conversation_id=hermes_conversation_id,
                    device_id=device_id,
                ):
                    speech = ""
                else:
                    speech = status.output
            elif status and status.status == "failed":
                _cancel_task(handoff_task)
                _LOGGER.warning("Hermes run failed before voice handoff: %s", status.output)
                speech = _UNAVAILABLE_SPEECH
            else:
                self.hass.async_create_task(
                    self._notify_when_run_finishes(
                        run.run_id,
                        request_text,
                        conversation_id=hermes_conversation_id,
                        device_id=device_id,
                    )
                )
                speech = await self._resolve_handoff_speech(handoff_task)
        except HermesAssistError as exc:
            _LOGGER.warning("Hermes voice request failed: %s", exc)
            speech = _UNAVAILABLE_SPEECH
        except Exception:
            _LOGGER.exception("Unexpected Hermes voice request failure")
            speech = _UNAVAILABLE_SPEECH

        intent_response = intent.IntentResponse(language=language or "en")
        intent_response.async_set_speech(speech)
        return conversation.ConversationResult(
            response=intent_response,
            conversation_id=conversation_id,
        )

    def _consume_pending_followup(
        self,
        user_input: conversation.ConversationInput,
    ) -> dict[str, Any] | None:
        """Return pending follow-up context for a short reply, if one applies."""
        text = getattr(user_input, "text", "") or ""
        if not _is_short_elliptical_reply(text):
            self._prune_expired_followups()
            return None
        keys = _followup_keys(
            getattr(user_input, "device_id", None),
            getattr(user_input, "conversation_id", None),
        )
        now = time.monotonic()
        for key in keys:
            pending = self._pending_followups.get(key)
            if not pending:
                continue
            if pending.get("expires_at", 0) < now:
                self._pending_followups.pop(key, None)
                continue
            # Remove every alias for this pending item so one reply cannot be
            # applied twice if HA reuses both device and conversation metadata.
            pending_id = pending.get("id")
            for stored_key, stored in list(self._pending_followups.items()):
                if stored.get("id") == pending_id:
                    self._pending_followups.pop(stored_key, None)
            return pending
        self._prune_expired_followups()
        return None

    def _store_pending_followup(
        self,
        *,
        request_text: str,
        followup_message: str,
        conversation_id: str | None,
        device_id: str | None,
    ) -> None:
        """Cache context so the next short satellite reply keeps continuity."""
        pending_id = f"{time.monotonic():.6f}"
        pending = {
            "id": pending_id,
            "request_text": request_text,
            "followup_message": followup_message,
            "conversation_id": conversation_id,
            "device_id": device_id,
            "expires_at": time.monotonic() + _PENDING_FOLLOWUP_TTL_SECONDS,
        }
        for key in _followup_keys(device_id, conversation_id):
            self._pending_followups[key] = dict(pending)

    def _prune_expired_followups(self) -> None:
        now = time.monotonic()
        for key, pending in list(self._pending_followups.items()):
            if pending.get("expires_at", 0) < now:
                self._pending_followups.pop(key, None)

    async def _start_immediate_followup_conversation_if_needed(
        self,
        message: str,
        *,
        request_text: str,
        conversation_id: str | None,
        device_id: str | None,
    ) -> bool:
        """Open a satellite reply window for immediate follow-up questions.

        Returning a follow-up as normal conversation speech makes the satellite
        ask and then stop listening. Starting a satellite conversation speaks the
        question through one path and keeps the microphone open for the answer.
        """
        followup_message = _followup_message(message)
        if not await self._start_followup_conversation_if_needed(followup_message):
            return False
        self._store_pending_followup(
            request_text=request_text,
            followup_message=followup_message,
            conversation_id=conversation_id,
            device_id=device_id,
        )
        return True

    def _start_handoff_task(
        self,
        request_text: str,
        *,
        language: str | None,
        device_name: str | None,
    ) -> asyncio.Task[str] | None:
        """Start handoff generation in parallel with the main Hermes run."""
        if not self._handoff_model or self._handoff_timeout <= 0:
            return None
        return self.hass.async_create_task(
            self._generate_handoff_speech(
                request_text,
                language=language,
                device_name=device_name,
            )
        )

    async def _resolve_handoff_speech(self, task: asyncio.Task[str] | None) -> str:
        """Return a ready contextual handoff without adding voice latency."""
        if task is None:
            return _HANDOFF_SPEECH
        if not task.done():
            return _HANDOFF_SPEECH
        try:
            return task.result() or _HANDOFF_SPEECH
        except Exception:
            _LOGGER.exception("Unexpected Hermes handoff task failure")
            return _HANDOFF_SPEECH

    async def _generate_handoff_speech(
        self,
        request_text: str,
        *,
        language: str | None,
        device_name: str | None,
    ) -> str:
        """Generate a contextual handoff phrase, falling back safely."""
        if not self._handoff_model or self._handoff_timeout <= 0:
            return _HANDOFF_SPEECH
        try:
            handoff = await self._client.async_generate_handoff(
                request_text,
                model=self._handoff_model,
                timeout=self._handoff_timeout,
                language=language,
                device_name=device_name,
            )
        except HermesAssistError as exc:
            _LOGGER.warning("Hermes handoff generation failed: %s", exc)
            return _HANDOFF_SPEECH
        except Exception:
            _LOGGER.exception("Unexpected Hermes handoff generation failure")
            return _HANDOFF_SPEECH
        return handoff or _HANDOFF_SPEECH

    async def _wait_for_run(self, run_id: str, timeout: float) -> HermesRunStatus | None:
        """Poll a Hermes run until it finishes or the voice wait expires."""
        if timeout <= 0:
            return None
        deadline = self.hass.loop.time() + timeout
        while self.hass.loop.time() < deadline:
            status = await self._client.async_get_run(run_id)
            if status.is_terminal or status.status == "waiting_for_approval":
                return status
            await asyncio.sleep(min(_RUN_POLL_INTERVAL, max(0, deadline - self.hass.loop.time())))
        return None

    async def _notify_when_run_finishes(
        self,
        run_id: str,
        request_text: str,
        *,
        conversation_id: str | None,
        device_id: str | None,
    ) -> None:
        """Create a Home Assistant notification when a background Hermes run completes."""
        deadline = self.hass.loop.time() + _RUN_BACKGROUND_TIMEOUT
        while self.hass.loop.time() < deadline:
            try:
                status = await self._client.async_get_run(run_id)
            except HermesAssistError as exc:
                _LOGGER.warning("Could not poll Hermes run %s: %s", run_id, exc)
                return
            if status.status == "completed":
                await self._deliver_background_result(
                    "Hermes finished working",
                    status.output or f"Hermes completed: {request_text}",
                    request_text=request_text,
                    conversation_id=conversation_id,
                    device_id=device_id,
                )
                return
            if status.status == "waiting_for_approval":
                await self._deliver_background_result(
                    "Hermes needs approval",
                    f"Hermes needs approval to continue: {request_text}",
                    request_text=request_text,
                    conversation_id=conversation_id,
                    device_id=device_id,
                )
                return
            if status.status in {"failed", "cancelled"}:
                await self._deliver_background_result(
                    "Hermes run did not complete",
                    status.output or f"Hermes run {status.status}: {request_text}",
                    request_text=request_text,
                    conversation_id=conversation_id,
                    device_id=device_id,
                )
                return
            await asyncio.sleep(_RUN_POLL_INTERVAL)
        await self._deliver_background_result(
            "Hermes is still working",
            f"Hermes is still working on: {request_text}",
            request_text=request_text,
            conversation_id=conversation_id,
            device_id=device_id,
        )

    async def _deliver_background_result(
        self,
        title: str,
        message: str,
        *,
        request_text: str = "",
        conversation_id: str | None = None,
        device_id: str | None = None,
    ) -> None:
        """Deliver a completed background run to notification and optional tablet."""
        await self._create_notification(title, message)
        tablet_message = _background_tablet_message(title, message)
        if await self._start_followup_conversation_if_needed(tablet_message):
            self._store_pending_followup(
                request_text=request_text,
                followup_message=_followup_message(tablet_message),
                conversation_id=conversation_id,
                device_id=device_id,
            )
            return
        if await self._announce_to_tablet(tablet_message):
            return
        await self._speak_to_tablet(tablet_message)

    async def _start_followup_conversation_if_needed(self, message: str) -> bool:
        """Start an Assist satellite conversation when the result asks a follow-up."""
        if not self._completion_announce_entity or not _looks_like_followup_question(message):
            return False
        try:
            await self.hass.services.async_call(
                "assist_satellite",
                "start_conversation",
                {"start_message": _followup_message(message)},
                target={"entity_id": self._completion_announce_entity},
                blocking=False,
            )
            return True
        except Exception:
            _LOGGER.exception(
                "Could not start Hermes follow-up conversation on %s",
                self._completion_announce_entity,
            )
            return False

    async def _announce_to_tablet(self, message: str) -> bool:
        if not self._completion_announce_entity:
            return False
        try:
            await self.hass.services.async_call(
                "assist_satellite",
                "announce",
                {"message": message},
                target={"entity_id": self._completion_announce_entity},
                blocking=False,
            )
            return True
        except Exception:
            _LOGGER.exception(
                "Could not announce Hermes completion to %s",
                self._completion_announce_entity,
            )
            return False

    async def _speak_to_tablet(self, message: str) -> bool:
        if not self._completion_tts_entity or not self._completion_media_player_entity:
            return False
        try:
            service_data = {
                "media_player_entity_id": self._completion_media_player_entity,
                "message": message,
                "cache": False,
            }
            if self._completion_tts_language:
                service_data["language"] = self._completion_tts_language
            if self._completion_tts_voice:
                service_data["options"] = {"voice": self._completion_tts_voice}
            await self.hass.services.async_call(
                "tts",
                "speak",
                service_data,
                target={"entity_id": self._completion_tts_entity},
                blocking=False,
            )
            return True
        except Exception:
            _LOGGER.exception(
                "Could not speak Hermes completion via %s to %s",
                self._completion_tts_entity,
                self._completion_media_player_entity,
            )
            return False

    async def _create_notification(self, title: str, message: str) -> None:
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": title,
                "message": message,
                "notification_id": "hermes_assist_background_run",
            },
            blocking=False,
        )

    def _device_name(self, user_input: conversation.ConversationInput) -> str | None:
        device_id = getattr(user_input, "device_id", None)
        if not device_id:
            return None
        try:
            device_registry = dr.async_get(self.hass)
            device = device_registry.async_get(device_id)
            return device.name if device else None
        except Exception:
            return None


def _cancel_task(task: asyncio.Task[Any] | None) -> None:
    """Cancel a best-effort background task and suppress expected cancellation noise."""
    if task is not None and not task.done():
        task.cancel()


def _background_tablet_message(title: str, message: str) -> str:
    """Return a concise tablet/TTS message while preserving the full notification."""
    clean_message = _normalize_message(message)
    full_message = _tablet_message(clean_message)
    if len(clean_message) <= _LONG_RESULT_TRIGGER_CHARS and _line_count(clean_message) <= 8:
        return full_message

    followup_question = _extract_followup_question(clean_message)
    summary_source = clean_message
    if followup_question:
        summary_source = clean_message[: -len(followup_question)].rstrip()
    summary = _short_summary(summary_source)
    parts = [summary]
    parts.append(f"I saved the full report in {_FULL_REPORT_LOCATION}.")
    if followup_question:
        parts.append(followup_question)
    return _trim_message(" ".join(part for part in parts if part))


def _short_summary(message: str) -> str:
    """Extract a short operational summary from a longer result."""
    lines = [
        line.strip(" -*•\t")
        for line in _normalize_message(message).splitlines()
        if line.strip(" -*•\t")
    ]
    useful_lines = [
        line
        for line in lines
        if not line.lower().startswith(("home assistant health check", "summary", "details"))
    ] or lines
    if not useful_lines:
        return "I finished the check."
    summary = "; ".join(useful_lines[:2])
    if len(summary) > 220:
        summary = f"{summary[:219].rstrip()}…"
    if not summary.endswith((".", "!", "?", "…")):
        summary += "."
    return summary


def _extract_followup_question(message: str) -> str:
    """Extract a trailing actionable follow-up question, if present."""
    text = _normalize_message(message)
    if not _looks_like_followup_question(text):
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        if _looks_like_followup_question(line):
            return line
    markers = ["Want me to", "Would you like me to", "Should I", "Shall I", "Do you want me to"]
    for marker in markers:
        index = text.rfind(marker)
        if index >= 0:
            return text[index:].strip()
    return text


def _normalize_message(message: str) -> str:
    return "\n".join(line.rstrip() for line in (message or "").strip().splitlines())


def _line_count(message: str) -> int:
    return sum(1 for line in (message or "").splitlines() if line.strip())


def _trim_message(message: str, max_chars: int = _TABLET_MESSAGE_MAX_CHARS) -> str:
    text = " ".join((message or "").strip().split())
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}…"


def _looks_like_followup_question(message: str) -> bool:
    """Return true when a background result appears to invite a spoken reply."""
    text = (message or "").strip()
    if not text.endswith("?"):
        return False
    lowered = text.lower()
    followup_markers = (
        "want me to",
        "would you like me to",
        "should i",
        "shall i",
        "do you want me to",
        "would you like",
        "should we",
        "want to",
    )
    return any(marker in lowered for marker in followup_markers)


def _is_short_elliptical_reply(text: str) -> bool:
    """Return true for replies that need previous-question context."""
    clean = " ".join((text or "").strip().lower().strip(".?!").split())
    if not clean:
        return False
    if len(clean.split()) > _SHORT_REPLY_MAX_WORDS:
        return False
    confirmation_markers = (
        "yes",
        "yes please",
        "yeah",
        "yep",
        "please do",
        "do it",
        "go ahead",
        "sure",
        "ok",
        "okay",
        "no",
        "no thanks",
        "not now",
        "cancel",
        "don't",
        "dont",
        "leave it",
        "turn it off",
        "turn it on",
    )
    if clean in confirmation_markers:
        return True
    return clean.startswith(("yes ", "yeah ", "yep ", "no ", "ok ", "okay "))


def _followup_keys(device_id: str | None, conversation_id: str | None) -> list[str]:
    """Return lookup keys from most specific to broad fallback."""
    keys: list[str] = []
    if device_id:
        keys.append(f"device:{device_id}")
    if conversation_id:
        keys.append(f"conversation:{conversation_id}")
    keys.append("global")
    return keys


def _followup_reply_prompt(reply: str, pending: dict[str, Any] | None) -> str:
    """Build a Hermes input that preserves the previous spoken question."""
    if not pending:
        return reply
    lines = [
        "Home Assistant Assist follow-up reply.",
        "The user is replying to a previous spoken follow-up question.",
    ]
    request_text = str(pending.get("request_text") or "").strip()
    followup_message = str(pending.get("followup_message") or "").strip()
    if request_text:
        lines.append(f"Previous user request: {request_text}")
    if followup_message:
        lines.append(f"Previous Hermes follow-up question: {followup_message}")
    lines.append(f"User reply: {reply}")
    lines.append(
        "Interpret short confirmations or denials in the context of the previous question. "
        "If confirmed, perform the implied action; if denied, acknowledge briefly."
    )
    return "\n".join(lines)


def _followup_message(message: str) -> str:
    """Return a concise start-conversation prompt for the satellite."""
    text = " ".join((message or "").strip().split())
    if len(text) <= _FOLLOWUP_QUESTION_MAX_CHARS:
        return text
    return f"{text[: _FOLLOWUP_QUESTION_MAX_CHARS - 1].rstrip()}…"


def _tablet_message(message: str) -> str:
    """Return a tablet-friendly message that is safe to display and speak."""
    full_message = (message or "").strip()
    if len(full_message) <= _TABLET_MESSAGE_MAX_CHARS:
        return full_message
    return f"{full_message[: _TABLET_MESSAGE_MAX_CHARS - 1].rstrip()}…"


def _entry_api_url(data: dict[str, Any]) -> str:
    """Resolve the Hermes API URL from new host/port fields or legacy api_url."""
    if CONF_API_HOST in data:
        return build_chat_completions_url(
            data.get(CONF_API_HOST, DEFAULT_API_HOST),
            data.get(CONF_API_PORT, DEFAULT_API_PORT),
        )
    return data[CONF_API_URL]
