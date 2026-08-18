from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import HermesAssistClient, HermesAssistError, build_chat_completions_url
from .form_helpers import config_flow_form_defaults
from .const import (
    CONF_API_HOST,
    CONF_API_PORT,
    CONF_API_TOKEN,
    CONF_MODEL,
    CONF_HANDOFF_MODEL,
    CONF_HANDOFF_TIMEOUT,
    CONF_COMPLETION_ANNOUNCE_ENTITY,
    CONF_COMPLETION_MEDIA_PLAYER_ENTITY,
    CONF_COMPLETION_TTS_ENTITY,
    CONF_SYSTEM_PROMPT,
    CONF_TIMEOUT,
    CONF_VOICE_WAIT_TIMEOUT,
    DEFAULT_MODEL,
    DEFAULT_HANDOFF_MODEL,
    DEFAULT_HANDOFF_TIMEOUT,
    DEFAULT_COMPLETION_ANNOUNCE_ENTITY,
    DEFAULT_COMPLETION_MEDIA_PLAYER_ENTITY,
    DEFAULT_COMPLETION_TTS_ENTITY,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TIMEOUT,
    DEFAULT_VOICE_WAIT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class HermesAssistConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Hermes Assist config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id("hermes_assist")
            self._abort_if_unique_id_configured()
            try:
                session = async_get_clientsession(self.hass)
                client = HermesAssistClient(
                    session,
                    api_url=build_chat_completions_url(
                        user_input[CONF_API_HOST], user_input[CONF_API_PORT]
                    ),
                    api_token=user_input[CONF_API_TOKEN],
                    model=user_input[CONF_MODEL],
                    timeout=user_input[CONF_TIMEOUT],
                    system_prompt=user_input[CONF_SYSTEM_PROMPT],
                )
                await client.async_validate()
            except (HermesAssistError, ValueError) as exc:
                _LOGGER.warning("Hermes validation failed: %s", exc)
                errors["base"] = "cannot_connect"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected Hermes validation failure")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or "Hermes Assist",
                    data=user_input,
                )

        defaults = config_flow_form_defaults(user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=defaults[CONF_NAME]): str,
                    vol.Required(CONF_API_HOST, default=defaults[CONF_API_HOST]): str,
                    vol.Required(CONF_API_PORT, default=defaults[CONF_API_PORT]): vol.Coerce(int),
                    vol.Required(CONF_API_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                    vol.Optional(CONF_MODEL, default=defaults[CONF_MODEL]): str,
                    vol.Optional(CONF_TIMEOUT, default=defaults[CONF_TIMEOUT]): vol.Coerce(int),
                    vol.Optional(
                        CONF_VOICE_WAIT_TIMEOUT,
                        default=defaults[CONF_VOICE_WAIT_TIMEOUT],
                    ): vol.Coerce(int),
                    vol.Optional(
                        CONF_SYSTEM_PROMPT,
                        default=defaults[CONF_SYSTEM_PROMPT],
                    ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return the options flow for Hermes Assist."""
        return HermesAssistOptionsFlowHandler()


class HermesAssistOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Hermes Assist options."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage Hermes Assist options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = self.config_entry.data
        options = self.config_entry.options
        prompt = options.get(
            CONF_SYSTEM_PROMPT,
            data.get(CONF_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT),
        )
        model = options.get(CONF_MODEL, data.get(CONF_MODEL, DEFAULT_MODEL))
        timeout = options.get(CONF_TIMEOUT, data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT))
        voice_wait_timeout = options.get(
            CONF_VOICE_WAIT_TIMEOUT,
            data.get(CONF_VOICE_WAIT_TIMEOUT, DEFAULT_VOICE_WAIT_TIMEOUT),
        )
        handoff_model = options.get(
            CONF_HANDOFF_MODEL,
            data.get(CONF_HANDOFF_MODEL, DEFAULT_HANDOFF_MODEL),
        )
        handoff_timeout = options.get(
            CONF_HANDOFF_TIMEOUT,
            data.get(CONF_HANDOFF_TIMEOUT, DEFAULT_HANDOFF_TIMEOUT),
        )
        completion_announce_entity = options.get(
            CONF_COMPLETION_ANNOUNCE_ENTITY,
            data.get(CONF_COMPLETION_ANNOUNCE_ENTITY, DEFAULT_COMPLETION_ANNOUNCE_ENTITY),
        )
        completion_tts_entity = options.get(
            CONF_COMPLETION_TTS_ENTITY,
            data.get(CONF_COMPLETION_TTS_ENTITY, DEFAULT_COMPLETION_TTS_ENTITY),
        )
        completion_media_player_entity = options.get(
            CONF_COMPLETION_MEDIA_PLAYER_ENTITY,
            data.get(
                CONF_COMPLETION_MEDIA_PLAYER_ENTITY,
                DEFAULT_COMPLETION_MEDIA_PLAYER_ENTITY,
            ),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_MODEL, default=model): str,
                    vol.Optional(CONF_TIMEOUT, default=timeout): vol.Coerce(int),
                    vol.Optional(CONF_VOICE_WAIT_TIMEOUT, default=voice_wait_timeout): vol.Coerce(int),
                    vol.Optional(CONF_HANDOFF_MODEL, default=handoff_model): str,
                    vol.Optional(CONF_HANDOFF_TIMEOUT, default=handoff_timeout): vol.Coerce(int),
                    vol.Optional(
                        CONF_COMPLETION_ANNOUNCE_ENTITY,
                        default=completion_announce_entity,
                    ): str,
                    vol.Optional(
                        CONF_COMPLETION_TTS_ENTITY,
                        default=completion_tts_entity,
                    ): str,
                    vol.Optional(
                        CONF_COMPLETION_MEDIA_PLAYER_ENTITY,
                        default=completion_media_player_entity,
                    ): str,
                    vol.Optional(
                        CONF_SYSTEM_PROMPT,
                        default=prompt,
                    ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
                }
            ),
        )
