# Plan: Web API Server (PL_WEB)

> **ID:** PL_WEB
> **Status:** completed
> **Implements:** SP_WEB
> **Changelog:** Initialized from existing codebase via onboard procedure (2026-04-22)

## Technology Decisions

- **Framework:** FastAPI — chosen for Pydantic validation, OpenAPI docs, and ASGI support
- **Server:** uvicorn[standard] with ASGI (asyncio) event loop
- **JSON:** orjson via custom ORJSONResponse — numpy array serialization, faster than stdlib json
- **Compression:** GZipMiddleware (min_size=500) — compresses frame responses
- **CORS:** allow_origins=["*"] — development setting; appropriate for localhost use
- **Static files:** FileResponse per-file (no StaticFiles mount) — simple, sufficient for dev

## Implementation Phases

- [DONE] FastAPI app setup with middleware
- [DONE] ConnectReq + ConfigReq Pydantic models
- [DONE] All REST endpoints
- [DONE] Frame polling with 5s wait logic
- [DONE] Hex format encoding + measurements per frame
- [DONE] Static file serving
- [DONE] ASGI entrypoint (main.py at project root)

## Backlog

- Convert api_frames to async endpoint with asyncio.sleep (Issue #4)
- Remove legacy `client = service._client` reference (Issue #6)
- Consider mounting StaticFiles for directory-level serving instead of per-file handler
- Expose V/div and T/div step lists via a config options endpoint (Issue #3)
