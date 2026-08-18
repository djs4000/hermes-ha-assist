from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

_CLIENT_PATH = Path(__file__).parents[1] / "custom_components" / "hermes_assist" / "client.py"
_SPEC = spec_from_file_location("hermes_assist_client", _CLIENT_PATH)
client = module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
sys.modules[_SPEC.name] = client
_SPEC.loader.exec_module(client)


def test_normalize_chat_completions_url():
    assert client.normalize_chat_completions_url("http://host:8642") == "http://host:8642/v1/chat/completions"
    assert client.normalize_chat_completions_url("http://host:8642/v1") == "http://host:8642/v1/chat/completions"
    assert client.normalize_chat_completions_url("http://host:8642/v1/chat/completions") == "http://host:8642/v1/chat/completions"


def test_extract_speech_from_openai_chat_response():
    data = {"choices": [{"message": {"content": "It is 8 AM."}}]}
    assert client.extract_speech(data) == "It is 8 AM."


def test_extract_speech_from_content_parts():
    data = {"choices": [{"message": {"content": [{"text": "hello"}, {"text": " world"}]}}]}
    assert client.extract_speech(data) == "hello world"
