from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import HermesAssistClient, HermesAssistError
from .form_helpers import config_flow_form_defaults
from .const import (
    CONF_API_TOKEN,
    CONF_API_URL,
    CONF_MODEL,
    CONF_SYSTEM_PROMPT,
    CONF_TIMEOUT,
    DEFAULT_SYSTEM_PROMPT,
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
                    api_url=user_input[CONF_API_URL],
                    api_token=user_input[CONF_API_TOKEN],
                    model=user_input[CONF_MODEL],
                    timeout=user_input[CONF_TIMEOUT],
                    system_prompt=DEFAULT_SYSTEM_PROMPT,
                )
                await client.async_validate()
            except HermesAssistError as exc:
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
                    vol.Required(CONF_API_URL, default=defaults[CONF_API_URL]): str,
                    vol.Required(CONF_API_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                    vol.Optional(CONF_MODEL, default=defaults[CONF_MODEL]): str,
                    vol.Optional(CONF_TIMEOUT, default=defaults[CONF_TIMEOUT]): vol.Coerce(int),
                }
            ),
            errors=errors,
        )


    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return the options flow for Hermes Assist."""
        return HermesAssistOptionsFlowHandler(config_entry)


class HermesAssistOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Hermes Assist options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage Hermes Assist options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        prompt = self.config_entry.options.get(
            CONF_SYSTEM_PROMPT,
            self.config_entry.data.get(CONF_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SYSTEM_PROMPT,
                        default=prompt,
                    ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
                }
            ),
        )
