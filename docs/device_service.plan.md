# Plan: Device Service (PL_DSV)

> **ID:** PL_DSV
> **Status:** completed
> **Implements:** SP_DSV
> **Changelog:** Initialized from existing codebase via onboard procedure (2026-04-22)

## Technology Decisions

- **Concurrency:** `threading.RLock` (reentrant) for device access; `threading.Lock` for frame buffer and config cache
- **Serialization:** `ThreadPoolExecutor(max_workers=1)` for all hardware commands — ensures FIFO ordering with timeout
- **Frame buffer:** `collections.deque(maxlen=256)` — O(1) append, automatic eviction of old frames
- **Acquisition loop pace:** 5ms sleep between frames — ~200Hz max polling rate
- **Auto-heal:** 5 consecutive errors → forced disconnect

## Implementation Phases

- [DONE] Device lifecycle (connect/disconnect with executor)
- [DONE] ensure_connected (smart reconnect)
- [DONE] Background acquisition loop with error counting
- [DONE] Frame buffer with seq numbering
- [DONE] Config snapshot and caching
- [DONE] apply_config with T1 bitfield manipulation
- [DONE] SW mode and sync type mappings
- [DONE] get_frames with since-based incremental retrieval
- [DONE] ensure_frame_available for auto-adjust

## Backlog

- Add `t_step_ms` to frame payload to fix auto_adjust_t_div (Issue #1)
- `_snapshot_config_locked()` reads every register on every frame — consider caching individual registers and only re-reading after config changes
- Async rewrite of acquisition would allow `asyncio.sleep` instead of blocking `time.sleep` in route handlers
- The `client = service._client` pattern in main.py should be removed (Issue #6)
