from pathlib import Path

CONFIG_FLOW = Path(__file__).parents[1] / "custom_components" / "hermes_assist" / "config_flow.py"
CONVERSATION = Path(__file__).parents[1] / "custom_components" / "hermes_assist" / "conversation.py"
STRINGS = Path(__file__).parents[1] / "custom_components" / "hermes_assist" / "strings.json"


def test_setup_uses_host_port_and_includes_system_prompt():
    source = CONFIG_FLOW.read_text()
    initial_schema = source.split("return self.async_show_form", 1)[1].split("errors=errors", 1)[0]

    assert "CONF_API_HOST" in initial_schema
    assert "CONF_API_PORT" in initial_schema
    assert "CONF_API_URL" not in initial_schema
    assert "CONF_SYSTEM_PROMPT" in initial_schema
    assert "selector.TextSelectorConfig(multiline=True)" in initial_schema


def test_options_flow_allows_tuning_prompt_model_and_timeout():
    source = CONFIG_FLOW.read_text()
    options_schema = source.split("class HermesAssistOptionsFlowHandler", 1)[1]

    assert "CONF_SYSTEM_PROMPT" in options_schema
    assert "CONF_MODEL" in options_schema
    assert "CONF_TIMEOUT" in options_schema


def test_runtime_prefers_options_for_model_timeout_and_system_prompt():
    source = CONVERSATION.read_text()

    assert "entry.options.get(CONF_MODEL, data.get(CONF_MODEL, DEFAULT_MODEL))" in source
    assert "entry.options.get(CONF_TIMEOUT, data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT))" in source
    assert "entry.options.get(" in source
    assert "CONF_SYSTEM_PROMPT, data.get(CONF_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT)" in source


def test_strings_rename_model_label_to_hermes_api_model_id():
    strings = STRINGS.read_text()

    assert "Hermes API model ID" in strings
    assert '"model": "Model"' not in strings
    assert "Hermes URL" in strings
    assert "Hermes API port" in strings
