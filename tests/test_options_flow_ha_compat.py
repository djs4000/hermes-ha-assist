from pathlib import Path

CONFIG_FLOW = Path(__file__).parents[1] / "custom_components" / "hermes_assist" / "config_flow.py"


def test_options_flow_does_not_assign_readonly_config_entry_property():
    source = CONFIG_FLOW.read_text()

    assert "return HermesAssistOptionsFlowHandler()" in source
    assert "self.config_entry = config_entry" not in source
    assert "def __init__(self, config_entry" not in source
