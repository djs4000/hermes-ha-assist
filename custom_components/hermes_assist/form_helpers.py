from __future__ import annotations

CONF_NAME = "name"
CONF_API_URL = "api_url"
CONF_MODEL = "model"
CONF_SYSTEM_PROMPT = "system_prompt"
CONF_TIMEOUT = "timeout"

DEFAULT_API_URL = "http://127.0.0.1:8642/v1/chat/completions"
DEFAULT_MODEL = "hermes-agent"
DEFAULT_TIMEOUT = 24
DEFAULT_SYSTEM_PROMPT = (
    "You are Hermes, responding through Home Assistant Assist. "
    "Reply naturally and concisely for text-to-speech. "
    "If the request involves smart-home control, perform the action through your configured tools. "
    "After answering a question, when it would be reasonable for the user to continue the discussion, "
    "end with a short natural question that invites a follow-up. "
    "Do not do this for simple smart-home commands such as turning lights on or off."
)


def config_flow_form_defaults(user_input: dict | None) -> dict:
    """Return safe form defaults for the config flow.

    Preserve non-secret values after validation errors so users do not have to
    retype URLs or long prompts. Deliberately omit the API token so Home
    Assistant does not echo secrets back into the form.
    """
    user_input = user_input or {}
    return {
        CONF_NAME: user_input.get(CONF_NAME, "Hermes Assist"),
        CONF_API_URL: user_input.get(CONF_API_URL, DEFAULT_API_URL),
        CONF_MODEL: user_input.get(CONF_MODEL, DEFAULT_MODEL),
        CONF_TIMEOUT: user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        CONF_SYSTEM_PROMPT: user_input.get(CONF_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT),
    }
