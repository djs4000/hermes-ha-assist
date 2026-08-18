from __future__ import annotations

CONF_NAME = "name"
CONF_API_HOST = "api_host"
CONF_API_PORT = "api_port"
CONF_API_URL = "api_url"
CONF_API_TOKEN = "api_token"
CONF_MODEL = "model"
CONF_SYSTEM_PROMPT = "system_prompt"
CONF_TIMEOUT = "timeout"

DEFAULT_API_HOST = "http://127.0.0.1"
DEFAULT_API_PORT = 8642
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
    """Return setup defaults while deliberately excluding secret values."""
    user_input = user_input or {}
    return {
        CONF_NAME: user_input.get(CONF_NAME, "Hermes Assist"),
        CONF_API_HOST: user_input.get(CONF_API_HOST, DEFAULT_API_HOST),
        CONF_API_PORT: user_input.get(CONF_API_PORT, DEFAULT_API_PORT),
        # Legacy fallback for tests/old callers; the setup form no longer shows it.
        CONF_API_URL: user_input.get(CONF_API_URL, DEFAULT_API_URL),
        CONF_MODEL: user_input.get(CONF_MODEL, DEFAULT_MODEL),
        CONF_TIMEOUT: user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        CONF_SYSTEM_PROMPT: user_input.get(CONF_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT),
    }
