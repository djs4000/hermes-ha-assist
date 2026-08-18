DOMAIN = "hermes_assist"

# New setup fields. Keep CONF_API_URL as a legacy storage key for entries created
# before host/port were split.
CONF_API_HOST = "api_host"
CONF_API_PORT = "api_port"
CONF_API_URL = "api_url"
CONF_API_TOKEN = "api_token"
CONF_MODEL = "model"
CONF_TIMEOUT = "timeout"
CONF_VOICE_WAIT_TIMEOUT = "voice_wait_timeout"
CONF_HANDOFF_MODEL = "handoff_model"
CONF_HANDOFF_TIMEOUT = "handoff_timeout"
CONF_COMPLETION_ANNOUNCE_ENTITY = "completion_announce_entity"
CONF_COMPLETION_TTS_ENTITY = "completion_tts_entity"
CONF_COMPLETION_MEDIA_PLAYER_ENTITY = "completion_media_player_entity"
CONF_COMPLETION_TTS_LANGUAGE = "completion_tts_language"
CONF_COMPLETION_TTS_VOICE = "completion_tts_voice"
CONF_SYSTEM_PROMPT = "system_prompt"

DEFAULT_API_HOST = "http://127.0.0.1"
DEFAULT_API_PORT = 8642
DEFAULT_MODEL = "hermes-agent"
DEFAULT_TIMEOUT = 24
DEFAULT_VOICE_WAIT_TIMEOUT = 10
DEFAULT_HANDOFF_MODEL = "openai-codex:gpt-5.4-mini"
DEFAULT_HANDOFF_TIMEOUT = 10
DEFAULT_HANDOFF_SPEECH = "Let me check on that. I’ll send the result when it’s done."
DEFAULT_COMPLETION_ANNOUNCE_ENTITY = ""
DEFAULT_COMPLETION_TTS_ENTITY = ""
DEFAULT_COMPLETION_MEDIA_PLAYER_ENTITY = ""
DEFAULT_COMPLETION_TTS_LANGUAGE = "en_GB"
DEFAULT_COMPLETION_TTS_VOICE = "en_GB-jenny_dioco-medium"
DEFAULT_SYSTEM_PROMPT = (
    "You are Hermes, responding through Home Assistant Assist. "
    "Reply naturally and concisely for text-to-speech. "
    "If the request involves smart-home control, perform the action through your configured tools. "
    "After answering a question, when it would be reasonable for the user to continue the discussion, "
    "end with a short natural question that invites a follow-up. "
    "Do not do this for simple smart-home commands such as turning lights on or off."
)

DEFAULT_API_URL = f"{DEFAULT_API_HOST}:{DEFAULT_API_PORT}/v1/chat/completions"
