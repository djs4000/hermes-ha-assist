from __future__ import annotations

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
    HermesTimeoutError,
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
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    DEFAULT_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
_TIMEOUT_SPEECH = "I’m sorry, Hermes is taking too long for a voice response. Try again more specifically, or send it to me in chat."
_UNAVAILABLE_SPEECH = "I’m sorry, Hermes is not available right now."


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
            response = await self._client.async_ask(
                user_input.text,
                conversation_id=conversation_id,
                language=language,
                device_name=device_name,
            )
            speech = response.speech
        except HermesTimeoutError:
            _LOGGER.warning("Hermes voice request timed out")
            speech = _TIMEOUT_SPEECH
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
