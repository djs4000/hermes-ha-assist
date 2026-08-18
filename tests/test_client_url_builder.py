from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

_CLIENT_PATH = Path(__file__).parents[1] / "custom_components" / "hermes_assist" / "client.py"
_SPEC = spec_from_file_location("hermes_assist_client_url_builder", _CLIENT_PATH)
client = module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
sys.modules[_SPEC.name] = client
_SPEC.loader.exec_module(client)


def test_build_chat_completions_url_from_host_and_port():
    assert client.build_chat_completions_url("http://192.168.1.148", 8642) == "http://192.168.1.148:8642/v1/chat/completions"
    assert client.build_chat_completions_url("http://192.168.1.148/", "8642") == "http://192.168.1.148:8642/v1/chat/completions"
    assert client.build_chat_completions_url("https://hermes.example.com/base", 9443) == "https://hermes.example.com:9443/base/v1/chat/completions"


def test_normalize_preserves_legacy_api_url():
    assert client.normalize_chat_completions_url("http://host:8642") == "http://host:8642/v1/chat/completions"
