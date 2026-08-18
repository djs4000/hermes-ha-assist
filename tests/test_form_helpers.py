from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

_HELPERS_PATH = Path(__file__).parents[1] / "custom_components" / "hermes_assist" / "form_helpers.py"
_SPEC = spec_from_file_location("hermes_assist_form_helpers", _HELPERS_PATH)
form_helpers = module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
sys.modules[_SPEC.name] = form_helpers
_SPEC.loader.exec_module(form_helpers)


def test_form_defaults_preserve_non_secret_values_after_validation_error():
    user_input = {
        "name": "Hermes Assist Dev",
        "api_host": "http://192.168.1.148",
        "api_port": 8642,
        "api_token": "super-secret-token",
        "model": "hermes-agent",
        "timeout": 18,
        "system_prompt": "A long custom prompt\nwith multiple lines.",
    }

    defaults = form_helpers.config_flow_form_defaults(user_input)

    assert defaults["name"] == "Hermes Assist Dev"
    assert defaults["api_host"] == "http://192.168.1.148"
    assert defaults["api_port"] == 8642
    assert defaults["model"] == "hermes-agent"
    assert defaults["timeout"] == 18
    assert defaults["system_prompt"] == "A long custom prompt\nwith multiple lines."
    assert "api_token" not in defaults


def test_form_defaults_use_initial_values_without_user_input():
    defaults = form_helpers.config_flow_form_defaults(None)

    assert defaults["name"] == "Hermes Assist"
    assert defaults["api_host"] == "http://127.0.0.1"
    assert defaults["api_port"] == 8642
    assert defaults["model"] == "hermes-agent"
    assert defaults["timeout"] == 24
    assert "api_token" not in defaults
