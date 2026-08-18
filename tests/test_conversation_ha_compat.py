from pathlib import Path

CONVERSATION = Path(__file__).parents[1] / "custom_components" / "hermes_assist" / "conversation.py"


def test_conversation_uses_helper_intent_response_for_current_ha():
    source = CONVERSATION.read_text()

    assert "intent" in source
    assert "intent.IntentResponse" in source
    assert "conversation.IntentResponse" not in source
