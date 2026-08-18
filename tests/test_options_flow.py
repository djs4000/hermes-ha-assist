from pathlib import Path

CONFIG_FLOW = Path(__file__).parents[1] / "custom_components" / "hermes_assist" / "config_flow.py"
CONVERSATION = Path(__file__).parents[1] / "custom_components" / "hermes_assist" / "conversation.py"


def test_initial_config_flow_does_not_show_system_prompt():
    source = CONFIG_FLOW.read_text()
    initial_schema = source.split("return self.async_show_form", 1)[1].split("errors=errors", 1)[0]

    assert "CONF_SYSTEM_PROMPT" not in initial_schema


def test_options_flow_configures_system_prompt_multiline():
    source = CONFIG_FLOW.read_text()

    assert "class HermesAssistOptionsFlowHandler" in source
    assert "async_get_options_flow" in source
    assert "CONF_SYSTEM_PROMPT" in source
    assert "selector.TextSelectorConfig(multiline=True)" in source


def test_conversation_prefers_system_prompt_from_options():
    source = CONVERSATION.read_text()

    assert "entry.options.get(CONF_SYSTEM_PROMPT" in source
    assert "data.get(CONF_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT)" in source
