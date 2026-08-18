# Hermes HA Assist

A clean Home Assistant custom integration that exposes Hermes Agent as a Home Assistant Assist conversation agent using Hermes' existing HTTP API.

This intentionally does **not** use a persistent WebSocket for voice requests. Home Assistant sends each spoken/text query as an independent HTTP request to Hermes' OpenAI-compatible API and receives a single speech response.

## Why

The previous WebSocket spike proved the concept, but request/response voice turns do not need a long-lived connection. This integration is designed to be simpler and more reliable:

- no persistent WebSocket reconnect state
- bounded HTTP request timeout below HA's voice timeout
- graceful spoken fallback when Hermes is slow/unavailable
- stable conversation/session headers so Hermes can keep context
- no new Hermes-side code required

## Requirements

- Home Assistant with custom integrations enabled
- Hermes Agent API server enabled and reachable from Home Assistant
- Hermes `API_SERVER_KEY` or equivalent bearer token

Hermes default API URL is usually:

```text
http://<hermes-host>:8642/v1/chat/completions
```

## Install manually

Copy the integration folder into Home Assistant:

```bash
custom_components/hermes_assist -> /config/custom_components/hermes_assist
```

Restart Home Assistant, then add the integration from **Settings → Devices & services → Add integration → Hermes Assist**.

## Configuration fields

- **Hermes API URL**: Base URL or full chat-completions URL. Examples:
  - `http://192.168.1.148:8642`
  - `http://192.168.1.148:8642/v1`
  - `http://192.168.1.148:8642/v1/chat/completions`
- **API token**: Hermes API bearer token.
- **Model**: usually `hermes-agent`.
- **Request timeout**: default 24 seconds, below Home Assistant's typical 30s Assist timeout.

## Development

```bash
uv run --with pytest --with pytest-asyncio python -m pytest -q
python3 -m compileall custom_components tests
```

## Status

Initial clean scaffold. The client and config flow are implemented; HA runtime validation should be tested inside Home Assistant before release.
