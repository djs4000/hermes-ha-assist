from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, intent
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
    CONF_MODEL,
    CONF_SYSTEM_PROMPT,
    CONF_TIMEOUT,
    CONF_VOICE_WAIT_TIMEOUT,
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    DEFAULT_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TIMEOUT,
    DEFAULT_VOICE_WAIT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
_HANDOFF_SPEECH = "Let me work on that. I’ll send the result as a Home Assistant notification when it’s done."
_UNAVAILABLE_SPEECH = "I’m sorry, Hermes is not available right now."
_RUN_POLL_INTERVAL = 1.0
_RUN_BACKGROUND_TIMEOUT = 300


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
        data = entry.data
        api_url = _entry_api_url(data)
        self._voice_wait_timeout = float(
            entry.options.get(
                CONF_VOICE_WAIT_TIMEOUT,
                data.get(CONF_VOICE_WAIT_TIMEOUT, DEFAULT_VOICE_WAIT_TIMEOUT),
            )
        )
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

    async def async_process(self, user_input: conversation.ConversationInput) -> conversation.ConversationResult:
        """Process a sentence through Hermes."""
        conversation_id = getattr(user_input, "conversation_id", None)
        language = getattr(user_input, "language", None)
        device_name = self._device_name(user_input)
        try:
            run = await self._client.async_start_run(
                user_input.text,
                conversation_id=conversation_id,
                language=language,
                device_name=device_name,
            )
            status = await self._wait_for_run(run.run_id, self._voice_wait_timeout)
            if status and status.status == "completed" and status.output:
                speech = status.output
            elif status and status.status == "failed":
                _LOGGER.warning("Hermes run failed before voice handoff: %s", status.output)
                speech = _UNAVAILABLE_SPEECH
            else:
                self.hass.async_create_task(
                    self._notify_when_run_finishes(run.run_id, user_input.text)
                )
                speech = _HANDOFF_SPEECH
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

    async def _notify_when_run_finishes(self, run_id: str, request_text: str) -> None:
        """Create a Home Assistant notification when a background Hermes run completes."""
        deadline = self.hass.loop.time() + _RUN_BACKGROUND_TIMEOUT
        while self.hass.loop.time() < deadline:
            try:
                status = await self._client.async_get_run(run_id)
            except HermesAssistError as exc:
                _LOGGER.warning("Could not poll Hermes run %s: %s", run_id, exc)
                return
            if status.status == "completed":
                await self._create_notification(
                    "Hermes finished working",
                    status.output or f"Hermes completed: {request_text}",
                )
                return
            if status.status == "waiting_for_approval":
                await self._create_notification(
                    "Hermes needs approval",
                    f"Hermes needs approval to continue: {request_text}",
                )
                return
            if status.status in {"failed", "cancelled"}:
                await self._create_notification(
                    "Hermes run did not complete",
                    status.output or f"Hermes run {status.status}: {request_text}",
                )
                return
            await asyncio.sleep(_RUN_POLL_INTERVAL)
        await self._create_notification(
            "Hermes is still working",
            f"Hermes is still working on: {request_text}",
        )

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


def _entry_api_url(data: dict[str, Any]) -> str:
    """Resolve the Hermes API URL from new host/port fields or legacy api_url."""
    if CONF_API_HOST in data:
        return build_chat_completions_url(
            data.get(CONF_API_HOST, DEFAULT_API_HOST),
            data.get(CONF_API_PORT, DEFAULT_API_PORT),
        )
    return data[CONF_API_URL]
