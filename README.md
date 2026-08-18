# Hermes HA Assist

A clean Home Assistant custom integration that exposes Hermes Agent as a Home Assistant Assist conversation agent using Hermes' existing HTTP API.

This intentionally does **not** use a persistent WebSocket for voice requests. Home Assistant starts each spoken/text query as a Hermes HTTP run, waits briefly for a fast answer, and hands longer work off to the background instead of letting Assist fail silently.

## Why

The previous WebSocket spike proved the concept, but request/response voice turns do not need a long-lived connection. This integration is designed to be simpler and more reliable:

- no persistent WebSocket reconnect state
- `/v1/runs` for Assist turns so long-running work can continue after the spoken response
- configurable short voice wait before handoff, default `10` seconds
- graceful AI-generated spoken fallback when Hermes is still working, with a static fallback if generation fails
- short tablet/TTS summaries for long background results, with the full report saved in a durable notification
- optional tablet/satellite completion announcement using `assist_satellite.announce` plus `tts.speak`
- automatic `assist_satellite.start_conversation` for background results that end with an actionable follow-up question
- stable conversation/session headers so Hermes can keep context

## Requirements

- Home Assistant with custom integrations enabled
- Hermes Agent API server enabled and reachable from Home Assistant
- Hermes `API_SERVER_KEY` bearer token

Hermes' documented local API endpoints are inferred from the URL and port you enter:

```text
http://<hermes-host>:<api-port>/v1/chat/completions
http://<hermes-host>:<api-port>/v1/runs
```

Example for a Hermes host at `192.168.1.148` using the default API port:

```text
http://192.168.1.148:8642/v1/runs
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
- **Request timeout seconds**: Default `24`; this bounds individual HTTP calls to Hermes.
- **Voice wait timeout seconds**: Default `10`; Assist waits this long for a run to finish before saying it will continue in the background.
- **Handoff model ID**: Optional. Set this to a Hermes API model alias for a cheap/fast model; when set, it is used for a contextual spoken handoff while the main run continues. Leave blank to use the static fallback phrase.
- **Handoff generation timeout seconds**: Default `2`; if the cheap model does not answer within this window, the static fallback phrase is used.
- **Completion Assist satellite entity**: Optional. If set, background run results are displayed with `assist_satellite.announce`, for example `assist_satellite.living_room_kiosk_tablet`.
- **Completion TTS entity**: Optional. TTS provider for speaking background results, for example `tts.piper`.
- **Completion media player entity**: Optional. Media player that should speak the TTS result, for example `media_player.living_room_kiosk_tablet_media_player`.
- **System prompt**: Optional prompt used for Home Assistant Assist responses.

After setup, open the integration's **Configure** / **Options** dialog to edit:

- **Hermes API model ID**
- **Request timeout seconds**
- **Voice wait timeout seconds**
- **Handoff model ID**
- **Handoff generation timeout seconds**
- **Completion Assist satellite entity**
- **Completion TTS entity**
- **Completion media player entity**
- **System prompt**

Connection-critical values — Hermes URL, API port, and API token — stay in the original setup entry.

## Long-running voice behavior

Assist turns use Hermes `/v1/runs`:

1. Home Assistant starts a Hermes run.
2. The integration polls for up to **Voice wait timeout seconds**.
3. If the run completes quickly, Assist speaks the answer.
4. If Hermes is still working, Assist asks the configured handoff model for a short contextual phrase such as `Let me check on that. I’ll send the result when it’s done.` If generation fails or is too slow, the static phrase is used.
5. The run continues in the background and the integration creates a Home Assistant persistent notification containing the full result when it completes, fails, needs approval, or is still running after the background polling window.
6. If completion tablet entities are configured, ordinary short results are displayed with `assist_satellite.announce` and spoken through `tts.speak`.
7. For long results, such as health checks or research reports, the tablet gets a short summary plus `I saved the full report in Home Assistant notifications.` The full text stays in the notification.
8. If the background result ends with an actionable follow-up question, such as `Want me to repair the automations first?`, the integration uses `assist_satellite.start_conversation` on the configured satellite with the short summary and question, so the user can answer naturally.

This is intended for requests like health checks, diagnostics, searches, and other multi-step work that take longer than a comfortable voice response window.

## Legacy entries

Older config entries that stored a full `api_url` continue to work. New setup forms use the cleaner Hermes URL + API port fields and infer `/v1/chat/completions` plus `/v1/runs` automatically.

## Development

```bash
uv run --with pytest --with aiohttp python -m pytest -q
python3 -m compileall custom_components tests
```

## Status

Clean HTTP-based Home Assistant Assist integration for Hermes Agent. Runtime validation should still be performed inside Home Assistant after updating custom component files.
