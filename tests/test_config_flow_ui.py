from pathlib import Path

CONFIG_FLOW = Path(__file__).parents[1] / "custom_components" / "hermes_assist" / "config_flow.py"


def test_system_prompt_selector_is_multiline_without_text_type():
    source = CONFIG_FLOW.read_text()

    system_prompt_block = source.split("CONF_SYSTEM_PROMPT", 1)[1]
    assert "selector.TextSelectorConfig(multiline=True)" in system_prompt_block
    assert "type=selector.TextSelectorType.TEXT" not in system_prompt_block
