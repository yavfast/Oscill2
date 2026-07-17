# Implementation Plan: Bluetooth Connectivity via Transport Abstraction  {#PL_BTT}

> **Code:** PL_BTT
> **Status:** completed
> **Created:** 2026-07-17
> **Updated:** 2026-07-17
>
> **Concept:** [C_BTT](./bluetooth_transport.concept.md)
> **Specification:** [SP_BTT](./bluetooth_transport.sp.md)
> **Depends on:** none (extends existing SP_OCL / SP_DSV / SP_WEB implementations)
> **Used by:** —
>
> Introduce a transport seam in the Python OBEX driver and an RFCOMM transport so the backend can
> reach the Oscill over Bluetooth Classic (SPP) as well as USB serial, without changing OBEX
> framing or regressing the USB path.

## Goal

When complete: `web_oscill` can open an OBEX session to the Oscill DSO over Bluetooth
(RFCOMM/SPP) as an alternative to USB, selected per-connection (request/env), with the existing
USB serial path behaving identically. The web frontend inherits Bluetooth through the unchanged
HTTP API. (Restates the task Intent: wireless connectivity to the scope via this PC's Bluetooth,
USB unchanged.) The live OBEX-over-BT handshake ([C_BTT_DEC_05], [SP_BTT_05_03]) is proven in
the Verify phase.

## Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3.14 (project standard) | Matches `web_oscill` |
| RFCOMM link | stdlib `socket.AF_BLUETOOTH` / `BTPROTO_RFCOMM` | Verified present; no `pybluez`/root/`/dev/rfcomm` bind ([C_BTT_DEC_03]) |
| Transport interface | `abc.ABC` base class `Transport` | Explicit contract, `isinstance` checks, matches project OO style; rule `PythonOneClassPerFile` |
| Endpoint model | frozen `@dataclass` value types + `TransportKind` `Enum` | Immutable (SP_BTT invariant), typed, lightweight (no pydantic needed at this layer) |
| Serial link | keep `pyserial` inside `SerialTransport` | Behaviour-preserving extraction; USB-only baud/`0x91` stay here |
| SDP channel resolution | boundary `resolve_spp_channel`; mechanism deferred | [SP_BTT_DEC_02] open — safe fallback (explicit channel → SDP → ch.1) works regardless; leaning `sdptool` (now installed) |
| API validation | extend pydantic `ConnectReq` with optional fields | Backward-compatible; FastAPI-native |
| Tests | standalone scripts in `scripts/` with a fake transport | rule `PythonTestsAreStandaloneScripts`; no pytest; hardware-free unit + mock |

## Required Knowledge

| Kind | Ref | Applies to | Note |
|------|-----|-----------|------|
| rule | LayerDependencyDirection (must) | P1–P3 | Transport is Layer 0 (peer of OscillClient); no upward deps |
| rule | HardwareAccessOnlyThroughDeviceService (must) | P4–P5 | API touches DeviceService only, never a transport/client |
| rule | SingletonDeviceService (must) | P4 | connect stays on the single executor + `_dev_lock` |
| rule | PythonOneClassPerFile (prefer) | P1–P3 | one transport class per module |
| rule | PythonSnakeCaseForModulesAndFunctions (must) | P1–P6 | module/function naming |
| rule | DeviceServiceInternalVsPublicMethods (should) | P4 | `_connect_internal` in executor; public `connect` submits |
| rule | PythonCatchAndReraise500 (must) | P5 | route wraps errors as HTTPException(500) |
| rule | PythonDeviceServiceWarningsVsExceptions (should) | P3 | SDP-fallback appends a warning, does not raise |
| rule | PythonTypeHintsOnPublicFunctions (should) | P1–P4 | typed public transport/connect API |
| rule | PythonTestsAreStandaloneScripts (prefer) | P6 | `scripts/test_*.py` |
| skill (apply) | obex_protocol | P1 | current — OBEX framing MUST stay byte-identical |
| skill (apply) | python_fastapi_patterns | P4 | current — DeviceService executor/connect pattern |
| skill (create) | oscill_bluetooth_transport | after Verify | capture RFCOMM/SPP + channel-resolution procedure once proven on hardware |

## Progress

- [x] Phase 1 — Transport seam + SerialTransport (driver refactor)
- [x] Phase 2 — Endpoint model, factory, default resolver
- [x] Phase 3 — RfcommTransport + SPP channel resolution
- [x] Phase 4 — DeviceService.connect superset + env config
- [x] Phase 5 — Web API /api/connect extension
- [x] Phase 6 — Functional tests (unit + mock)
- [x] Phase 7 — Live verification ✅ **PASS 2026-07-17** (RFCOMM ch1 + OBEX + frame over BT)
- [x] Phase 8 — BT device discovery by name (paired-list) + `resolve_bt_address` layering
- [x] Phase 9 — DeviceService auto-connect (USB→BT) + `transport_kind` in status
- [x] Phase 10 — API `/api/connect` auto/serial/bluetooth modes + status `transport_kind`
- [x] Phase 11 — Frontend transport indicator + Auto/USB/BT picker
- [x] Phase 12 — Functional tests (name-discovery, auto-fallback order, transport_kind)

## Phases

### Phase 1 — Transport seam + SerialTransport (`web_oscill/transport.py`, `web_oscill/serial_transport.py`, refactor `web_oscill/oscill_client.py`) [TODO]

**Depends on:** none
**Implements:** [SP_BTT_01_03](./bluetooth_transport.sp.md#SP_BTT_01_03), [SP_BTT_01_04](./bluetooth_transport.sp.md#SP_BTT_01_04), [SP_BTT_02_01](./bluetooth_transport.sp.md#SP_BTT_02_01)–[SP_BTT_02_06](./bluetooth_transport.sp.md#SP_BTT_02_06); modifies SP_OCL driver construction
**Verify:** [SP_BTT_05_02](./bluetooth_transport.sp.md#SP_BTT_05_02) (OBEX framing byte-identical; serial path unregressed; `open()` re-entry guarded) + [SP_BTT_05_01](./bluetooth_transport.sp.md#SP_BTT_05_01) (read partial/empty via `_read_exact`) — plus: existing `scripts/test_connect.py` / `scripts/test_parse_frame.py` pass unchanged

What to create:
| Entity | Module | Purpose |
|--------|--------|---------|
| `Transport` (ABC) + `TransportCapabilities` + `TransportError`, `UnsupportedCapability` | `web_oscill/transport.py` | Byte-stream contract + capability descriptor + error types |
| `SerialTransport(Transport)` | `web_oscill/serial_transport.py` | Wraps `serial.Serial`; owns baud + `set_link_speed`; `supports_speed_change=True`; hosts `auto_find_port` (or re-export) |

Refactor in `oscill_client.py`:
- Replace `self.ser` with `self._transport: Transport`.
- `OscillClient(transport, timeout=3.0)` canonical; add `OscillClient.over_serial(port, baud=115200, timeout=3.0)` building a `SerialTransport` (preserves existing call sites' semantics).
- Map every `self.ser.*` site (init/open/close/reset/_read_exact/get_reg/get_data_single/set_reg/firmware/speed) to `self._transport.*` (read/write/reset_buffers/read_timeout).
- `raise_speed`/`restore_default_speed`/`set_speed`: guard on `self._transport.capabilities.supports_speed_change`; keep the `0x91` packet build (OBEX framing) in the driver; the host-baud switch goes through `transport.set_link_speed`.

Notes:
- **No OBEX framing change** (`_build_packet`, `_read_resp`, `_parse_headers`, register/command contracts untouched) — skill `obex_protocol`.
- `read` contract: returns `b""` on timeout (SerialTransport already does via `serial.read`).
- `close()` idempotent + never raises; `open()` re-open raises (keep existing guard).

### Phase 2 — Endpoint model, transport factory, default resolver (`web_oscill/endpoints.py`) [TODO]

**Depends on:** Phase 1
**Implements:** [SP_BTT_01_01](./bluetooth_transport.sp.md#SP_BTT_01_01), [SP_BTT_01_02](./bluetooth_transport.sp.md#SP_BTT_01_02), [SP_BTT_01_05](./bluetooth_transport.sp.md#SP_BTT_01_05), [SP_BTT_02_08](./bluetooth_transport.sp.md#SP_BTT_02_08), [SP_BTT_03_01](./bluetooth_transport.sp.md#SP_BTT_03_01)
**Verify:** [SP_BTT_05_01](./bluetooth_transport.sp.md#SP_BTT_05_01) (build_transport serial auto → DeviceNotFound if none) + [SP_BTT_05_04](./bluetooth_transport.sp.md#SP_BTT_05_04) (bad address / channel range / missing address → validation/ConfigError before I/O)

What to create:
| Entity | Module | Purpose |
|--------|--------|---------|
| `TransportKind(Enum)`, `SerialEndpoint`, `BluetoothEndpoint`, `ConnectionEndpoint` (union) | `web_oscill/endpoints.py` | Immutable connection descriptors + validation |
| `resolve_default_endpoint(port, baud)` | `web_oscill/endpoints.py` | Env-driven default (`OSCILL_TRANSPORT`/`OSCILL_BT_ADDR`/`OSCILL_BT_CHANNEL`) |
| `build_transport(endpoint, timeout)` | `web_oscill/endpoints.py` | Endpoint → open-able Transport (serial auto-detect; BT channel resolution deferred to Phase 3 fn) |

Notes:
- Validate BD_ADDR regex + channel 1..30 at construction; raise `ValueError`/`ConfigError` before any hardware access.
- `build_transport` for `bluetooth` calls `resolve_spp_channel` (Phase 3) when `channel is None`.

Pseudocode sketch:
    resolve_default_endpoint(port, baud):
        if port: return SerialEndpoint(port, baud)
        kind = env(OSCILL_TRANSPORT, "serial")
        if kind == "bluetooth": return BluetoothEndpoint(env(OSCILL_BT_ADDR)!, env(OSCILL_BT_CHANNEL)?)
        return SerialEndpoint(None, baud)

### Phase 3 — RfcommTransport + SPP channel resolution (`web_oscill/rfcomm_transport.py`) [TODO]

**Depends on:** Phase 1 (Transport ABC), Phase 2 (endpoint/factory hook)
**Implements:** [SP_BTT_02_02](./bluetooth_transport.sp.md#SP_BTT_02_02)–[SP_BTT_02_07](./bluetooth_transport.sp.md#SP_BTT_02_07) (RFCOMM realizations + `resolve_spp_channel`)
**Verify:** [SP_BTT_05_01](./bluetooth_transport.sp.md#SP_BTT_05_01) (read empty on timeout via fake; write complete over chunked sink; set_link_speed → UnsupportedCapability) + [SP_BTT_05_03](./bluetooth_transport.sp.md#SP_BTT_05_03) fallback-channel row

What to create:
| Entity | Module | Purpose |
|--------|--------|---------|
| `RfcommTransport(Transport)` | `web_oscill/rfcomm_transport.py` | RFCOMM socket link; `supports_speed_change=False` |
| `resolve_spp_channel(address) -> int` | `web_oscill/rfcomm_transport.py` | explicit → SDP → fallback ch.1 (warn) |

Notes:
- `open()`: `socket.socket(AF_BLUETOOTH, SOCK_STREAM, BTPROTO_RFCOMM)`; **set `BT_SECURITY_LOW`
  (insecure) via `setsockopt(SOL_BLUETOOTH=274, BT_SECURITY=4, pack("BB",1,0))` before connect**
  (verified required — default security stalls the device); `connect((address, channel))` with a
  connect timeout ≥8 s (RFCOMM bring-up ~3.5 s); then set blocking + `settimeout(read_timeout)`.
  Precondition: device OS-paired (PIN 0000). Lift this verbatim from `scripts/test_bt_quick.py`.
- `read(n)`: `settimeout(read_timeout)`; `recv` up to n; **translate `socket.timeout` → return `b""`** (never raise on timeout); raise `TransportError` on real socket error / peer gone.
- `write(data)`: full `sendall` loop (no short write).
- `reset_buffers()`: non-blocking drain of pending `recv` until empty.
- `set_link_speed`: raise `UnsupportedCapability` (never called — capability-gated in driver).
- `resolve_spp_channel`: mechanism per [SP_BTT_DEC_02] (leaning `sdptool browse`), with warn-and-fallback to channel 1; append warning (rule `PythonDeviceServiceWarningsVsExceptions` spirit).

Pseudocode sketch:
    RfcommTransport.read(n):
        assert is_open
        sock.settimeout(read_timeout)
        try: return sock.recv(n)
        except socket.timeout: return b""
        except OSError as e: raise TransportError(e)

### Phase 4 — DeviceService.connect superset + env config (`web_oscill/device_service.py`) [TODO]

**Depends on:** Phases 2, 3
**Implements:** [SP_BTT_02_09](./bluetooth_transport.sp.md#SP_BTT_02_09), [SP_BTT_01_05](./bluetooth_transport.sp.md#SP_BTT_01_05)
**Verify:** [SP_BTT_05_01](./bluetooth_transport.sp.md#SP_BTT_05_01) (legacy `connect("/dev/ttyUSB0",115200)` unchanged; BT happy path → connected, **no** speed-raise) + [SP_BTT_05_02](./bluetooth_transport.sp.md#SP_BTT_05_02) (speed-raise skipped on BT via fake) + error table [SP_BTT_02_09](./bluetooth_transport.sp.md#SP_BTT_02_09)

What to implement:
- `_connect_internal(endpoint | port/baud)`: build endpoint via `resolve_default_endpoint` when no endpoint; `build_transport`; `OscillClient(transport)`; `open_and_handshake()`; existing init sequence unchanged.
- Gate the post-init `raise_speed()` on `ep.kind == serial and OSCILL_HIGH_BAUD != 0` (capability-gated no-op even if reached on BT).
- Public `connect(endpoint=None, *, port=None, baud=115200)` submits to executor; `ensure_connected` delegates unchanged.
- Map errors: `DeviceNotFound` / `BluetoothUnreachable` / `ChannelResolutionError` / `ConfigError`.

Notes:
- Concurrency model untouched (executor + `_dev_lock`) — rules `SingletonDeviceService`, `DeviceServiceInternalVsPublicMethods`.
- Keep `close(restore=True)` path; on BT, `restore_default_speed` is a capability-gated no-op.

### Phase 5 — Web API /api/connect extension (`web_oscill/main.py`) [TODO]

**Depends on:** Phase 4
**Implements:** [SP_BTT_02_10](./bluetooth_transport.sp.md#SP_BTT_02_10)
**Verify:** [SP_BTT_05_01](./bluetooth_transport.sp.md#SP_BTT_05_01) (legacy `{port,baud}` unchanged; `{transport:"bluetooth",address}` connects) — plus: invalid `transport`/`address` → HTTPException(500) with actionable detail

What to implement:
- Extend `ConnectReq` with optional `transport`, `address`, `channel` (defaults null).
- `api_connect`: build `ConnectionEndpoint` from body (or env default) → `service.connect(endpoint)`; wrap errors `HTTPException(500, detail=str(e))` (rule `PythonCatchAndReraise500`).
- Preserve current behaviour when only `port`/`baud` (or nothing) is sent.

Notes:
- No frontend change required (concept scope); frontend transport picker is backlog.

### Phase 6 — Functional tests (`scripts/test_transport.py`, `scripts/test_bluetooth_connect.py`) [TODO]

**Depends on:** Phases 1–5
**Implements:** test coverage for [SP_BTT_05_01](./bluetooth_transport.sp.md#SP_BTT_05_01), [SP_BTT_05_02](./bluetooth_transport.sp.md#SP_BTT_05_02), [SP_BTT_05_04](./bluetooth_transport.sp.md#SP_BTT_05_04)
**Verify:** all new + existing serial tests pass; no hardware required

What to create:
| Test | Covers |
|------|--------|
| `FakeTransport` helper + `scripts/test_transport.py` | read-empty-on-timeout, write-complete, capability gating, `open()` re-entry, endpoint validation, `build_transport` serial-auto/DeviceNotFound |
| `scripts/test_bluetooth_connect.py` | DeviceService.connect over a fake BT transport: connects, **no** speed-raise; ConfigError on missing address; error mapping |

Notes:
- Use a `FakeTransport` implementing the `Transport` ABC (chunked byte sink/source) — hardware-free.
- OBEX-framing-unchanged check: build a packet through `OscillClient.over_serial` against a fake and assert bytes match a captured baseline.

### Phase 7 — Live verification (Verify phase) [DONE ✅ 2026-07-17]

**Depends on:** Phases 1–6; **hardware:** Oscill DSO powered + connectable + OS-paired
**Implements:** closes [C_BTT_DEC_05](./bluetooth_transport.concept.md#C_BTT_DEC_05)
**Verify:** [SP_BTT_05_03](./bluetooth_transport.sp.md#SP_BTT_05_03) (live handshake: connect → read version → acquire one frame; end-to-end via `/api/connect`)

**Result (2026-07-17):** `scripts/test_bt_quick.py --channel 1 --frame` → PASS. RFCOMM ch1
(insecure, `BT_SECURITY_LOW`) + OBEX CONNECT + properties (VNM=Uosc, VSN=6070, VHW=1.25,
VSW=1.26) + 252-sample NORMAL frame. Preconditions found: (a) reset host adapter after the
VirtualBox Win7 VM releases the USB dongle (`rfkill` cycle + `hciconfig reset`) — the VM grab
leaves HCI inquiry timing out; (b) OS-pair with PIN 0000. The `/api/connect` end-to-end path is
still to be exercised once Phases 4–5 land (the standalone script proved the driver path).

Return trigger: executed in the **Verify** phase when the scope is available. Also finalizes
[SP_BTT_DEC_02] (SDP mechanism) against the live device, and — if proven — harvests the
`oscill_bluetooth_transport` skill.

**Tooling ready (2026-07-17):** `scripts/test_bt_quick.py` — a standalone live diagnostic that
opens an RFCOMM socket and reuses the OBEX driver (via a `SocketSerial` shim) to run
CONNECT + read version properties (+ optional `--frame`). Validated for graceful failure
(scope off → "Host is down", rc=1). It **prototypes Phase 3** (`resolve_spp_channel` via
`sdptool`, RFCOMM read→`b""`-on-timeout / full-write) so Phase 3 can lift the proven logic.
Awaiting a powered/connectable scope for the live PASS.

## Phases (increment 2 — auto / discovery / UI)

### Phase 8 — BT device discovery by name (`web_oscill/rfcomm_transport.py`, `web_oscill/endpoints.py`) [TODO]

**Depends on:** Phases 1-3
**Implements:** [SP_BTT_02_11](./bluetooth_transport.sp.md#SP_BTT_02_11)
**Verify:** paired-list parse picks the `Oscill*` device by name; explicit/env address overrides; missing → ConfigError

- `find_paired_device_by_name(name_substr)` in `rfcomm_transport.py` — `bluetoothctl devices Paired` (fallback `paired-devices`), parse `Device <addr> <name>`, case-insensitive substring match.
- `resolve_bt_address(address)` + `resolve_bt_address_optional()` in `endpoints.py` — explicit → `OSCILL_BT_ADDR` → name match; raise/return-None respectively.
- `resolve_endpoint(transport="bluetooth", address=None)` now name-resolves the address.

### Phase 9 — DeviceService auto-connect + transport_kind (`web_oscill/device_service.py`) [TODO]

**Depends on:** Phase 8
**Implements:** [SP_BTT_02_12](./bluetooth_transport.sp.md#SP_BTT_02_12), [SP_BTT_02_09](./bluetooth_transport.sp.md#SP_BTT_02_09) (transport_kind)
**Verify:** auto tries USB then BT; first success wins; failed attempt torn down; `transport_kind` in status; disconnected→null

- Refactor `_connect_internal` body into `_open_and_init(ep)` (build → handshake → init → mark), tearing down `cli` on any failure.
- `connect_auto(baud)` → candidates `[serial-auto] + [bt if resolvable]`, budget = BT when BT present; `_connect_internal_auto` tries each until one connects.
- Track `self._transport_kind`; include in `get_status()` + connect response; clear on disconnect.
- `ensure_connected()` (no args) delegates to the auto path.

### Phase 10 — API connect modes + status transport_kind (`web_oscill/main.py`) [TODO]

**Depends on:** Phase 9
**Implements:** [SP_BTT_02_10](./bluetooth_transport.sp.md#SP_BTT_02_10)
**Verify:** `transport:"auto"`→auto; `"serial"`/`"bluetooth"` route correctly; BT with no address name-resolves; status carries transport_kind

- `ConnectReq.transport` accepts `auto`; route maps auto→`connect_auto`, serial/bluetooth→endpoint→`connect`.
- Default (no body) → auto.

### Phase 11 — Frontend transport indicator + picker (`web_oscill/static/…`) [TODO]

**Depends on:** Phase 10
**Implements:** UI requirement (show current transport; Auto/USB/BT picker)
**Verify:** indicator shows USB/BT when connected; picker drives connect over the chosen transport

- `statusBar.js` — append `· USB`/`· BT` to the Connected label from `status.transport_kind`.
- `index.html` — add a `#transport-select` (Auto/USB/BT) control in the status bar.
- `app.js` — read the picker; pass its mode to `api.connect`; auto-connect on load uses it.
- `api.js` — `connect({transport, address})` builds the body.

### Phase 12 — Functional tests (`scripts/test_transport.py`, `scripts/test_bluetooth_connect.py`) [TODO]

**Depends on:** Phases 8-10
**Verify:** name-discovery parse (match/none/override); auto-fallback order (USB→BT, BT skipped when no device); transport_kind reported

## Backlog

- Android concrete Bluetooth `ObexTransport` — return when: Android BT is explicitly requested ([C_BTT_DEC_02] excluded Android).
- Active BT **inquiry** scan for unpaired devices — return when: connecting to a never-paired scope is needed (pairing is currently an OS precondition — [SP_BTT_DEC_03]).

## Design Decisions  {#PL_BTT_DEC}

### DEC_01 — Transport module layout  {#PL_BTT_DEC_01}

> **Status:** resolved
> **Date:** 2026-07-17

**Question:** How to split the transport code across modules?

**Options considered:**
| Option | Consequence |
|--------|-------------|
| A — `transport.py` (ABC+errors+caps), `serial_transport.py`, `rfcomm_transport.py`, `endpoints.py` | One class/concern per file (rule `PythonOneClassPerFile`); clear Layer-0 grouping; more files |
| B — single `transport.py` with everything | Fewer files but violates one-class-per-file and mixes serial/BT concerns |

**Decision:** A — four focused modules.
**Rationale:** Honors `PythonOneClassPerFile`; isolates USB-only (`serial_transport`) from BT-only (`rfcomm_transport`) code as the concept requires; keeps the abstract contract dependency-free.
**Rejected because:** B re-mixes exactly the concerns the transport seam exists to separate.

### DEC_02 — SDP channel-resolution mechanism  {#PL_BTT_DEC_02}

> **Status:** resolved
> **Date:** 2026-07-17

**Question:** Which mechanism implements the SDP step inside `resolve_spp_channel`?

**Options considered:**
| Option | Consequence |
|--------|-------------|
| A — `sdptool browse` subprocess parse | No Python dep (tool now installed); needs device reachable for SDP |
| B — BlueZ D-Bus query | No subprocess; adds D-Bus dep + code |
| C — require explicit channel, skip SDP | Simplest; user supplies channel |

**Decision:** RESOLVED (2026-07-17) → **A (`sdptool`) + fallback**. Live-verified: `sdptool
records/browse` returns the SPP record (`Serial Port 0x1101`, channel 1) **while an ACL is
active**; empty otherwise → fall back to channel 1 (which is correct for this unit). Keep the
warned fallback per the dual-service caveat.
**Rationale:** Proven against the live device; no new dependency; safe fallback holds.
**Resolution trigger:** — (closed)

## Changelog

| Date | Change |
|------|--------|
| 2026-07-17 | Initial plan — 7 phases (seam+serial → endpoints → rfcomm → device_service → API → tests → live verify). DEC_02 (SDP mechanism) open → Verify. |
| 2026-07-17 | **Phase 7 DONE — live BT PASS.** DEC_02 resolved (sdptool + fallback). Phase 3 note: RFCOMM MUST set `BT_SECURITY_LOW` (insecure) + ≥8 s connect timeout; pair (PIN 0000) precondition; reset host adapter after VirtualBox releases the dongle. |
| 2026-07-17 | **Phases 1-6 DONE — plan completed.** transport.py/serial_transport.py/rfcomm_transport.py/endpoints.py + connect superset + `/api/connect` + hardware-free tests. Clean-context review PASS (fixed: BT executor budget 5s→50s; SDP parser targets SPP by 0x1101 UUID not service name). Propagated to SP_OCL/SP_DSV/SP_WEB. |
