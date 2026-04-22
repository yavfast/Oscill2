# Concept: Device Service (C_DSV)

> **ID:** C_DSV
> **Status:** active
> **Area:** Python backend
> **Changelog:** Initialized from existing codebase via onboard procedure (2026-04-22)

## Philosophy

`DeviceService` is the concurrency firewall between the web layer and the hardware. The device speaks one language at a time — you cannot ask it for a frame and change its config simultaneously. DeviceService enforces this with a single-threaded executor for all hardware commands and an RLock for the background acquisition loop. The web API makes no decisions about timing, threading, or state — it simply calls DeviceService methods.

## Domain Model

| Entity | Description |
|--------|-------------|
| Device connection | Single OscillClient instance; exactly one active at a time |
| Frame | One acquired waveform + timestamp + sequence number + snapshot config |
| Frame buffer | Bounded ring buffer (deque, maxlen=256); newest frame at index [-1] |
| Config snapshot | Immutable dict of all device parameters; updated after every change |
| Config ID (cfg_id) | Integer counter; increments on every config change; frontend uses this to detect stale UI |
| Acquisition loop | Background thread; continuously pulls frames and stores in buffer |

## Mechanisms

**Single-threaded executor:** All hardware I/O submits to a `ThreadPoolExecutor(max_workers=1)`. This serializes connect, disconnect, and apply_config calls without deadlocking with the acquisition loop.

**RLock for acquisition loop:** The background acquisition loop acquires `_dev_lock` with a 100ms timeout per iteration. Config operations hold the same lock. This prevents simultaneous device access.

**Frame buffering:** Frames are stored with a monotonically increasing `seq` number. The HTTP frontend polls `GET /api/frames?since=N` to get only new frames, avoiding re-processing.

**Config caching:** `get_status()` returns cached config — it never queries the device. Only `_snapshot_config_locked()` (called after connect and every apply_config) reads from hardware.

**Auto-healing:** After 5 consecutive acquisition errors, the loop forces a full disconnect to prevent infinite error storms.

## Integration Points

- **Depends on:** `oscill_client` (hardware I/O), `converters` (unit conversion in apply_config)
- **Used by:** `web_api/main` (all route handlers), `auto_adjust` (frame access + config mutation)
