# Concept: Web API Server (C_WEB)

> **ID:** C_WEB
> **Status:** active
> **Area:** Python backend
> **Changelog:** Initialized from existing codebase via onboard procedure (2026-04-22)

## Philosophy

The web API is the single HTTP boundary of the system. It exposes a simple REST interface that maps one-to-one onto DeviceService operations, handles protocol translation (JSON ↔ Python dicts, string enums ↔ integer register values), and serves the static web frontend. It owns no device state — all state lives in DeviceService.

## Domain Model

| Entity | Description |
|--------|-------------|
| REST endpoint | HTTP path + method pair, maps to one DeviceService operation |
| Config request | JSON body with optional parameter keys; only specified keys are applied |
| Frame response | Config snapshot + array of frames with measurements and hex-encoded samples |
| Auto-adjust request | Comma-separated list of adjustment types as query parameter |

## Mechanisms

**Incremental polling:** `GET /api/frames?since=N` returns only frames with seq > N. On empty buffer, waits up to 5s for frames to arrive (synchronous poll with sleep — acceptable for single-user dev use).

**Fast JSON:** Uses `ORJSONResponse` (orjson library) as default response class — handles numpy arrays and is ~3-5× faster than standard json.

**GZip:** Responses ≥500 bytes are compressed. All frame responses are compressed.

**Config ID:** Every response that includes config also includes `cfg_id`. The frontend uses this to detect config changes and update its UI state.

## Integration Points

- **Depends on:** `device_service`, `calculations`, `auto_adjust`, `converters`, `oscill_client`
- **Used by:** Web frontend (HTTP), uvicorn ASGI server
- **Serves:** Static files from `web_oscill/static/`
