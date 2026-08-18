from pathlib import Path

CLIENT = Path("custom_components/hermes_assist/client.py")
CONVERSATION = Path("custom_components/hermes_assist/conversation.py")
CONST = Path("custom_components/hermes_assist/const.py")
CONFIG_FLOW = Path("custom_components/hermes_assist/config_flow.py")
STRINGS = Path("custom_components/hermes_assist/strings.json")
ROOT_ICON = Path("icon.png")
INTEGRATION_ICON = Path("custom_components/hermes_assist/icon.png")


def test_hacs_icon_assets_exist():
    assert ROOT_ICON.exists()
    assert INTEGRATION_ICON.exists()
    assert ROOT_ICON.stat().st_size > 0
    assert INTEGRATION_ICON.stat().st_size > 0


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


def test_ai_handoff_generation_is_configurable_and_best_effort():
    const_source = CONST.read_text()
    config_source = CONFIG_FLOW.read_text()
    strings_source = STRINGS.read_text()
    client_source = CLIENT.read_text()
    conversation_source = CONVERSATION.read_text()

    assert 'CONF_HANDOFF_MODEL = "handoff_model"' in const_source
    assert 'CONF_HANDOFF_TIMEOUT = "handoff_timeout"' in const_source
    assert 'DEFAULT_HANDOFF_MODEL = "openai-codex:gpt-5.4-mini"' in const_source
    assert "parse_provider_prefixed_model" in client_source
    assert 'payload["provider"] = handoff_model.provider' in client_source
    assert "Handoff model ID" in strings_source
    assert "CONF_HANDOFF_MODEL" in config_source
    assert "async_generate_handoff" in client_source
    assert '"model_options": {"fast": True, "reasoning": {"enabled": False}}' in client_source
    assert "_start_handoff_task" in conversation_source
    assert "_resolve_handoff_speech" in conversation_source
    assert "normalize_handoff_speech" in client_source
    assert "_generate_handoff_speech" in conversation_source
    assert "Hermes handoff generation failed" in conversation_source


def test_completion_tablet_delivery_is_configurable():
    const_source = CONST.read_text()
    config_source = CONFIG_FLOW.read_text()
    strings_source = STRINGS.read_text()
    conversation_source = CONVERSATION.read_text()

    assert 'CONF_COMPLETION_ANNOUNCE_ENTITY = "completion_announce_entity"' in const_source
    assert 'CONF_COMPLETION_TTS_ENTITY = "completion_tts_entity"' in const_source
    assert 'CONF_COMPLETION_MEDIA_PLAYER_ENTITY = "completion_media_player_entity"' in const_source
    assert 'CONF_COMPLETION_TTS_LANGUAGE = "completion_tts_language"' in const_source
    assert 'CONF_COMPLETION_TTS_VOICE = "completion_tts_voice"' in const_source
    assert 'DEFAULT_COMPLETION_TTS_LANGUAGE = "en_GB"' in const_source
    assert 'DEFAULT_COMPLETION_TTS_VOICE = "en_GB-jenny_dioco-medium"' in const_source
    assert "CONF_COMPLETION_TTS_LANGUAGE" in config_source
    assert "CONF_COMPLETION_TTS_VOICE" in config_source
    assert "Completion Assist satellite entity" in strings_source
    assert "Completion TTS language" in strings_source
    assert "Completion TTS voice" in strings_source
    assert '"assist_satellite"' in conversation_source
    assert '"announce"' in conversation_source
    assert '"start_conversation"' in conversation_source
    assert "_background_tablet_message" in conversation_source
    assert 'parts = [f"{title}. {summary}"]' not in conversation_source
    assert 'full_message = f"{title}. {message}".strip()' not in conversation_source
    assert "I saved the full report" in conversation_source
    assert "_looks_like_followup_question" in conversation_source
    assert "_store_pending_followup" in conversation_source
    assert "_consume_pending_followup" in conversation_source
    assert "_followup_reply_prompt" in conversation_source
    duplicate_followup_tts = "await self._speak_to_tablet(_followup_message(tablet_message))"
    assert duplicate_followup_tts not in conversation_source
    assert '"tts"' in conversation_source
    assert '"speak"' in conversation_source
    assert "media_player_entity_id" in conversation_source
    assert 'service_data["language"] = self._completion_tts_language' in conversation_source
    assert 'service_data["options"] = {"voice": self._completion_tts_voice}' in conversation_source


def test_conversation_uses_runs_with_handoff_and_background_completion():
    source = CONVERSATION.read_text()

    const_source = CONST.read_text()

    assert "async_start_run" in source
    assert "async_get_run" in source
    assert "async_create_task" in source
    assert "Let me check on that" in const_source
    assert "persistent_notification" in source


def test_followup_context_helpers_detect_short_replies():
    source = CONVERSATION.read_text()

    assert "def _is_short_elliptical_reply" in source
    assert '"yes please"' in source
    assert '"not now"' in source
    assert "_SHORT_REPLY_MAX_WORDS" in source


def test_followup_delivery_uses_single_speech_path():
    source = CONVERSATION.read_text()

    assert "assist_satellite" in source
    assert "start_conversation" in source
    assert "if await self._announce_to_tablet(tablet_message):" in source
    assert "return\n        await self._speak_to_tablet(tablet_message)" in source
    assert "await asyncio.sleep(0.75)" not in source
    assert "start_conversation" in source and "_store_pending_followup" in source


def test_background_completion_uses_announce_only_then_tts_fallback():
    source = CONVERSATION.read_text()

    assert "if await self._announce_to_tablet(tablet_message):" in source
    assert "return\n        await self._speak_to_tablet(tablet_message)" in source
    assert "await asyncio.sleep(0.75)" not in source
    assert "async def _announce_to_tablet(self, message: str) -> bool" in source
    assert "async def _speak_to_tablet(self, message: str) -> bool" in source


def test_immediate_followup_questions_keep_satellite_conversation_open():
    source = CONVERSATION.read_text()

    assert "_start_immediate_followup_conversation_if_needed" in source
    assert "Returning a follow-up as normal conversation speech" in source
    assert "speech = \"\"" in source
    assert "keeps the microphone open for the answer" in source
