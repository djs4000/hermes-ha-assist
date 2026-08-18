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
- Hermes `API_SERVER_KEY` bearer token

Hermes' documented local API endpoint is inferred from the URL and port you enter:

```text
http://<hermes-host>:<api-port>/v1/chat/completions
```

Example for a Hermes host at `192.168.1.148` using the default API port:

```text
http://192.168.1.148:8642/v1/chat/completions
```

## Install manually

Copy the integration folder into Home Assistant:

```bash
custom_components/hermes_assist -> /config/custom_components/hermes_assist
```

Restart Home Assistant, then add the integration from **Settings → Devices & services → Add integration → Hermes Assist**.

## Configuration fields

- **Hermes URL**: The base Hermes host URL, without the API path. Example: `http://192.168.1.148`.
- **Hermes API port**: Usually `8642`.
- **Hermes API token**: Hermes `API_SERVER_KEY` bearer token.
- **Hermes API model ID**: Usually `hermes-agent`. This is the OpenAI-compatible model identifier Hermes exposes, not necessarily the underlying LLM provider/model.
- **Request timeout seconds**: Default `24`, below Home Assistant's typical 30-second Assist timeout.
- **System prompt**: Optional prompt used for Home Assistant Assist responses.

After setup, open the integration's **Configure** / **Options** dialog to edit:

- **Hermes API model ID**
- **Request timeout seconds**
- **System prompt**

Connection-critical values — Hermes URL, API port, and API token — stay in the original setup entry.

## Legacy entries

Older config entries that stored a full `api_url` continue to work. New setup forms use the cleaner Hermes URL + API port fields and infer `/v1/chat/completions` automatically.

## Development

```bash
uv run --with pytest --with aiohttp python -m pytest -q
python3 -m compileall custom_components tests
```

## Status

Clean HTTP-based Home Assistant Assist integration for Hermes Agent. Runtime validation should still be performed inside Home Assistant after updating custom component files.
