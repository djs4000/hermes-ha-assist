from pathlib import Path

CLIENT = Path("custom_components/hermes_assist/client.py")
CONVERSATION = Path("custom_components/hermes_assist/conversation.py")
CONST = Path("custom_components/hermes_assist/const.py")
CONFIG_FLOW = Path("custom_components/hermes_assist/config_flow.py")
STRINGS = Path("custom_components/hermes_assist/strings.json")


def test_client_builds_runs_url_from_chat_completions_url():
    source = CLIENT.read_text()

    assert "def normalize_runs_url" in source
    assert "v1/runs" in source
    assert "self.runs_url = normalize_runs_url(self.api_url)" in source


def test_client_can_start_and_poll_hermes_runs():
    source = CLIENT.read_text()

    assert "async def async_start_run" in source
    assert "async def async_get_run" in source
    assert '"input": user_message' in source
    assert "self.runs_url" in source
    assert "f\"{self.runs_url}/{run_id}\"" in source


def test_voice_wait_timeout_is_configurable_with_default_10_seconds():
    const_source = CONST.read_text()
    config_source = CONFIG_FLOW.read_text()
    strings_source = STRINGS.read_text()

    assert 'CONF_VOICE_WAIT_TIMEOUT = "voice_wait_timeout"' in const_source
    assert "DEFAULT_VOICE_WAIT_TIMEOUT = 10" in const_source
    assert "CONF_VOICE_WAIT_TIMEOUT" in config_source
    assert "DEFAULT_VOICE_WAIT_TIMEOUT" in config_source
    assert "Voice wait timeout seconds" in strings_source


def test_conversation_uses_runs_with_handoff_and_background_completion():
    source = CONVERSATION.read_text()

    assert "async_start_run" in source
    assert "async_get_run" in source
    assert "async_create_task" in source
    assert "Let me work on that" in source
    assert "persistent_notification" in source
