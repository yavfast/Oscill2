# Bluetooth Connectivity via Transport Abstraction — Specification  {#SP_BTT}

> **Code:** SP_BTT
> **Status:** active
> **Created:** 2026-07-17
> **Updated:** 2026-07-17
>
> **Concept:** [C_BTT](./bluetooth_transport.concept.md)
> **Depends on:** [SP_OCL](./oscill_client.sp.md), [SP_DSV](./device_service.sp.md)
> **Used by:** [SP_WEB](./web_api.sp.md)
> **Plan:** [PL_BTT](./bluetooth_transport.plan.md)
>
> Defines the **Transport** abstraction that decouples the OBEX driver from its byte stream,
> its two implementations (**Serial** for USB, **RFCOMM** for Bluetooth Classic/SPP), the
> connection **endpoint** model, and the connect/config surface extensions that let a caller
> choose the link. OBEX framing (SP_OCL packet build/parse, register/command contracts) is
> unchanged; this spec only re-homes *where bytes enter and leave the driver* and adds the
> Bluetooth link.

## 01. Data Structures  {#SP_BTT_01}

> Implements: [C_BTT_02](./bluetooth_transport.concept.md#C_BTT_02)

### 01_01. TransportKind  {#SP_BTT_01_01}

Enumeration selecting the physical link.

| Value | Meaning |
|-------|---------|
| `serial` | USB serial (CP210x). Default; preserves all current behaviour. |
| `bluetooth` | Bluetooth Classic RFCOMM / Serial Port Profile (SPP). |

Invariants:
- Unknown values are rejected at the connect boundary (see [SP_BTT_03_01](#SP_BTT_03_01)).
- `serial` is the default whenever a caller supplies no kind.

### 01_02. ConnectionEndpoint  {#SP_BTT_01_02}

A discriminated union describing *where and how* to reach the device. Exactly one variant per
connection request. It is the single canonical input to the connection path; the legacy
`(port, baud)` form maps onto the serial variant.

**SerialEndpoint** (`kind = serial`):
| Field | Type | Required | Default | Constraints | Description |
|-------|------|----------|---------|-------------|-------------|
| `kind` | TransportKind | yes | `serial` | = `serial` | Discriminator |
| `port` | string \| null | no | null | OS device path or null | Serial device path; **null ⇒ auto-detect** (CP210x VID/PID scan, existing `auto_find_port`) |
| `baud` | int | no | 115200 | > 0 | Initial baud; the driver may raise it post-init (serial only) |

**BluetoothEndpoint** (`kind = bluetooth`):
| Field | Type | Required | Default | Constraints | Description |
|-------|------|----------|---------|-------------|-------------|
| `kind` | TransportKind | yes | `bluetooth` | = `bluetooth` | Discriminator |
| `address` | string | yes | — | BD_ADDR `XX:XX:XX:XX:XX:XX` (6 hex octets, colon-separated, case-insensitive) | Device Bluetooth address |
| `channel` | int \| null | no | null | 1..30 when set | RFCOMM channel; **null ⇒ resolve via SDP** (SPP UUID `0x1101`), then fall back per [SP_BTT_02_07](#SP_BTT_02_07) |

Invariants:
- `SerialEndpoint.port = null` triggers auto-detect; a non-null port is used verbatim.
- `BluetoothEndpoint.address` is mandatory (no BT auto-discovery in this spec — see [SP_BTT_DEC_03](#SP_BTT_DEC_03)).
- The endpoint is immutable once a connection is opened from it.

### 01_03. TransportCapabilities  {#SP_BTT_01_03}

Static capability descriptor a transport exposes so the driver can adapt without knowing the
concrete link type.

| Field | Type | Serial | RFCOMM | Description |
|-------|------|--------|--------|-------------|
| `supports_speed_change` | bool | `true` | `false` | Whether `set_link_speed` is meaningful; gates the `0x91` speed-raise sequence |

Invariant: capabilities are constant for the lifetime of a transport instance.

### 01_04. Transport (abstract)  {#SP_BTT_01_04}

The byte-stream contract consumed **only** by the OBEX driver (`OscillClient`). Replaces the
driver's direct `serial.Serial` handle (`self.ser`). Concrete state per implementation:

| Field | Type | Description |
|-------|------|-------------|
| `is_open` | bool | True between `open()` and `close()` |
| `read_timeout` | float (seconds) | Current blocking-read budget; get/set at runtime (the driver adjusts it per operation, e.g. acquisition wait) |
| `capabilities` | TransportCapabilities | See [SP_BTT_01_03](#SP_BTT_01_03) |

Contracts on this entity are defined in [SP_BTT_02](#SP_BTT_02).

### 01_05. Configuration keys (environment)  {#SP_BTT_01_05}

Consumed by the **default-endpoint resolver** ([SP_BTT_02_08](#SP_BTT_02_08)) when a caller
connects without specifying an endpoint (auto-connect / `ensure_connected`). Consistent with the
existing `OSCILL_*` convention.

| Key | Type | Default | Constraints | Description |
|-----|------|---------|-------------|-------------|
| `OSCILL_TRANSPORT` | string | `serial` | `serial` \| `bluetooth` | Default transport kind |
| `OSCILL_BT_ADDR` | string | unset | BD_ADDR format | Default Bluetooth device address (required if transport=bluetooth and no address passed) |
| `OSCILL_BT_CHANNEL` | int | unset | 1..30 | Default RFCOMM channel; unset ⇒ SDP resolve |

Invariant: `OSCILL_HIGH_BAUD` (existing) is honoured only on the serial transport; it is inert under `bluetooth` (capability-gated, [SP_BTT_02_05](#SP_BTT_02_05)).

## 02. Contracts  {#SP_BTT_02}

### 02_01. Transport.open / close  {#SP_BTT_02_01}

Purpose: establish / tear down the underlying byte stream.

| Operation | Input | Output | Errors |
|-----------|-------|--------|--------|
| `open()` | — | none | `TransportError` if the link cannot be established |
| `close()` | — | none | never raises (best-effort); idempotent |

Logic:
    FUNCTION open():
        IF is_open: RAISE TransportError("already open")
        establish link (serial port OR RFCOMM socket connect)
        set is_open = true
    FUNCTION close():
        best-effort tear down; set is_open = false   # safe to call when already closed

Invariants:
- `open()` on an already-open transport raises (mirrors the existing `OscillClient.open()` guard, [SP_OCL] connection lifecycle).
- `close()` is idempotent and never raises.

**RFCOMM `open()` requirements (verified on live hardware 2026-07-17):**
- **MUST use insecure RFCOMM** — set `BT_SECURITY_LOW` on the socket
  (`setsockopt(SOL_BLUETOOTH=274, BT_SECURITY=4, level=BT_SECURITY_LOW=1)`) **before** `connect`.
  With the default security level the kernel tries to elevate authentication/encryption on
  connect and the Oscill stalls → connect timeout. This matches the old Android app's
  `createInsecureRfcommSocket` (`ConnectInsecure`).
- **Precondition: the device must be OS-paired/bonded** first (PIN `0000`). Unbonded, the connect
  times out. Pairing is done once in the OS (BlueZ / `bluetoothctl`), not by this software.
- Connect latency is ~3.5 s (normal for RFCOMM bring-up); the connect timeout must allow for it
  (≥8 s recommended).

### 02_02. Transport.read  {#SP_BTT_02_02}

Purpose: read up to `n` bytes, bounded by `read_timeout`.

Input: `n: int` (> 0). Output: `bytes` of length `0..n`.

**Critical invariant (preserves SP_OCL `_read_exact` semantics):** on timeout with no data,
`read` returns `b""` (empty) — it **must not raise**. The driver's `_read_exact` loop treats an
empty return as "stop"; a partial return as "continue". This holds identically for both links.

Logic:
    FUNCTION read(n):
        ASSERT is_open
        block up to read_timeout for up to n bytes
        RETURN whatever arrived (possibly empty, possibly < n)

Errors:
| Code | Condition | Guidance |
|------|-----------|----------|
| `TransportError` | link dropped mid-read (peer gone, socket error) | surfaces to the acquisition loop → self-healing disconnect ([`AcquisitionLoopSelfHealingDisconnect`]) |

### 02_03. Transport.write  {#SP_BTT_02_03}

Purpose: write all bytes to the link.

Input: `data: bytes`. Output: none.

Invariant: **all** bytes are written before returning (serial write is blocking; RFCOMM uses a
full send loop). A short write is never silently dropped.

Errors: `TransportError` if the link is closed or the peer is gone.

### 02_04. Transport.reset_buffers  {#SP_BTT_02_04}

Purpose: discard any pending inbound/outbound bytes (used by the driver's `reset()` around an
OBEX ABORT and by the speed-switch path).

Input: none. Output: none. Never raises when open.

Logic:
    FUNCTION reset_buffers():
        serial:  reset_input_buffer(); reset_output_buffer()
        rfcomm:  drain socket recv (non-blocking) until empty

Note: the OBEX-level ABORT packet itself stays in the driver's `reset()`; this contract covers
only the transport-level buffer drain.

### 02_05. Transport.set_link_speed  {#SP_BTT_02_05}

Purpose: change the host-side link speed (serial baud). **Capability-gated.**

Input: `baud: int` (> 0). Output: none.

| Implementation | Behaviour |
|----------------|-----------|
| Serial | Sets the port baudrate to `baud`, flushes buffers. |
| RFCOMM | **No-op** by contract (`supports_speed_change = false`); the driver never calls it because it checks the capability first. If called directly, raises `UnsupportedCapability`. |

This is the contract realisation of [C_BTT_DEC_04](./bluetooth_transport.concept.md#C_BTT_DEC_04):
the `0x91` OBEX speed-raise packet (SP_OCL) is still built by the driver, but the entire
`raise_speed` / `restore_default_speed` sequence is skipped when `capabilities.supports_speed_change`
is false.

### 02_06. Transport.describe  {#SP_BTT_02_06}

Purpose: a stable, human-readable label for logs and error messages.

Output: `string`, e.g. `serial:/dev/ttyUSB0@115200` or `bluetooth:20:13:04:24:20:55/ch1`.

### 02_07. resolve_spp_channel  {#SP_BTT_02_07}

Purpose: determine the RFCOMM channel of the device's SPP service.

Input: `address: string` (BD_ADDR). Output: `int` (channel 1..30).

Resolution order (first that succeeds wins):
1. If the endpoint/config supplied an explicit `channel`, use it (no lookup).
2. **SDP query** for the Serial Port service (UUID `0x1101`) on `address` via the available
   system Bluetooth facility; take the returned RFCOMM channel.
3. **Fallback** to channel `1` (the common SPP default), logging a warning that SDP resolution
   did not run/return. (Verified: the Oscill DSO's Serial Port service *is* on channel 1, service
   name "Dev B" — so the fallback happens to be correct for this unit, but must stay a warned
   last resort per the dual-service caveat below.)

**SDP note (verified):** `sdptool browse/records` returns the SPP record only while an **ACL link
is active** to the device; with no live connection it returns empty. Resolution should therefore
tolerate an empty SDP result (→ fallback) rather than treating it as an error.

**Dual-service caveat (verified from `oscilobex.pdf`):** the Oscill advertises **two** Bluetooth
services — *Object Push* **and** *Serial Port (SPP)*. OBEX for control runs over **Serial Port**.
Because a wrong service could sit on a low channel, the fallback-to-1 in step 3 is a
best-effort last resort only; step 2 (SDP targeting the **Serial Port** record specifically) is
strongly preferred and is the sole way to be certain the channel is SPP, not Object Push. When
step 3 is used, the warning must state that the channel is unverified.

Errors:
| Code | Condition | Guidance |
|------|-----------|----------|
| `ChannelResolutionError` | SDP ran, device reachable, but exposes **no** SPP service | Device may not be in the right mode; verify it is the Oscill and powered/connectable |

Note: mirrors the Windows reference — `BT_SearchSPPExServices` (search the SPP service) →
`Btsdk_GetAvailableExtSPPCOMPort` (bind it as a virtual COM port) → OBEX, all handled by WCL.
The concrete SDP mechanism (system tool vs. platform API) is a plan-level choice
([SP_BTT_DEC_02](#SP_BTT_DEC_02)).

### 02_08. Connection endpoint resolution & driver construction  {#SP_BTT_02_08}

Purpose: turn a `ConnectionEndpoint` (or the legacy `(port, baud)` / env defaults) into an open
OBEX driver bound to the right transport. Realises [C_BTT_03_01](./bluetooth_transport.concept.md#C_BTT_03_01)
(transport selection) and modifies the [SP_OCL] connection lifecycle.

**Driver construction (modifies SP_OCL):** the OBEX driver is constructed **over a Transport**
rather than a `(port, baud)` pair.

    OscillClient(transport: Transport, timeout: float = 3.0)          # new canonical
    OscillClient.over_serial(port, baud=115200, timeout=3.0)          # backward-compat helper
        → OscillClient(SerialTransport(port, baud, timeout))

All `self.ser.*` uses in the driver are replaced by `self._transport.*` (read/write/reset_buffers/
read_timeout). `auto_find_port` stays as a serial concern used when building a SerialTransport
with a null port. **No OBEX framing changes.**

**Default-endpoint resolver:**
    FUNCTION resolve_default_endpoint(port, baud):
        IF port is not null: RETURN SerialEndpoint(port, baud)          # explicit legacy call
        kind = env OSCILL_TRANSPORT or "serial"
        IF kind == "bluetooth":
            addr = env OSCILL_BT_ADDR  (REQUIRED → else ConfigError)
            ch   = env OSCILL_BT_CHANNEL or null
            RETURN BluetoothEndpoint(addr, ch)
        RETURN SerialEndpoint(null, baud)                              # serial auto-detect

**Transport factory:**
    FUNCTION build_transport(endpoint, timeout):
        IF endpoint.kind == serial:
            port = endpoint.port or OscillClient.auto_find_port()
            IF port is null: RAISE DeviceNotFound
            RETURN SerialTransport(port, endpoint.baud, timeout)
        IF endpoint.kind == bluetooth:
            channel = endpoint.channel or resolve_spp_channel(endpoint.address)
            RETURN RfcommTransport(endpoint.address, channel, timeout)

### 02_09. DeviceService.connect (modified)  {#SP_BTT_02_09}

> Modifies [SP_DSV] connect contract.

Purpose: connect over any transport, serialised through the existing single-worker executor +
`_dev_lock` (unchanged concurrency model — [`SingletonDeviceService`], [`HardwareAccessOnlyThroughDeviceService`]).

Input (backward-compatible superset):
| Parameter | Type | Required | Default | Constraints |
|-----------|------|----------|---------|-------------|
| `endpoint` | ConnectionEndpoint \| null | no | null | when set, used verbatim |
| `port` | string \| null | no | null | legacy serial path (used only if `endpoint` is null) |
| `baud` | int | no | 115200 | legacy serial baud |

Output: unchanged status dict (`status`, `is_connected`, `is_acquiring`, device info…).

Logic:
    FUNCTION connect(endpoint=null, port=null, baud=115200):
        IF already connected: RETURN get_status()
        ep = endpoint or resolve_default_endpoint(port, baud)
        transport = build_transport(ep, timeout)
        client = OscillClient(transport)
        client.open_and_handshake()          # OBEX CONNECT — identical for both links
        ... existing init (cpu freq, RS mode, defaults, timebase) unchanged ...
        IF ep.kind == serial AND OSCILL_HIGH_BAUD != 0: client.raise_speed()   # capability-gated no-op on BT
        mark connected; RETURN status

Errors:
| Code | Condition | Guidance |
|------|-----------|----------|
| `DeviceNotFound` | serial auto-detect found no CP210x | connect USB or specify port |
| `BluetoothUnreachable` | RFCOMM connect failed ("Host is down"/refused) | power on & make the scope connectable; pair it in the OS first |
| `ChannelResolutionError` | no SPP service on device (see 02_07) | verify device identity/mode |
| `ConfigError` | transport=bluetooth but no address (env/request) | set `OSCILL_BT_ADDR` or pass `address` |

`ensure_connected` delegates to `connect` with the same superset (env defaults apply when nothing is passed).

### 02_10. Web API — POST /api/connect (extended)  {#SP_BTT_02_10}

> Modifies [SP_WEB]. Backward-compatible: existing `{port, baud}` bodies behave exactly as before.

Request body (`ConnectReq`, all fields optional):
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `transport` | string | null | `serial` \| `bluetooth`; null ⇒ server default (env) |
| `port` | string | null | serial path (serial only) |
| `baud` | int | 115200 | serial baud (serial only) |
| `address` | string | null | BD_ADDR (bluetooth only; required for bluetooth if no env default) |
| `channel` | int | null | RFCOMM channel (bluetooth only; null ⇒ SDP resolve) |

Mapping: the route builds a `ConnectionEndpoint` from the body (or falls back to env defaults)
and calls `DeviceService.connect(endpoint)`. Errors map to `HTTPException(500, detail=str(e))`
per [`PythonCatchAndReraise500`]; the detail carries the actionable message from the connect
error table above.

Output: unchanged status JSON.

## 03. Validation Rules  {#SP_BTT_03}

### 03_01. Input Validation  {#SP_BTT_03_01}

- `transport` accepts only `serial` / `bluetooth` (case-insensitive); any other value → validation error before any hardware access.
- `address` must match `^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$`; rejected otherwise.
- `channel`, when present, is an integer in `1..30`; out-of-range rejected.
- For `transport = bluetooth`, an address must be resolvable (request field **or** `OSCILL_BT_ADDR`); otherwise `ConfigError`.
- For `transport = serial`, `port` may be null (auto-detect) or a non-empty string.
- All read/write on a transport require `is_open` (assertion), preserving the SP_OCL invariant that connect precedes I/O.

## 04. State Transitions  {#SP_BTT_04}

### 04_01. Transport lifecycle  {#SP_BTT_04_01}

State diagram:
    [closed] --open()--> [open] --close()--> [closed]
       ^                    |
       └────── close() ─────┘   (idempotent; open→open on re-open() raises)

Transition rules:
| From | To | Condition | Side effects |
|------|----|-----------|-------------|
| closed | open | link established | `is_open=true`; serial opens port, rfcomm connects socket |
| open | open | `open()` called again | **rejected** (`TransportError`) — mirrors existing guard |
| open | closed | `close()` | buffers released; `is_open=false` |
| closed | closed | `close()` | no-op (idempotent) |

### 04_02. Speed state (serial only)  {#SP_BTT_04_02}

Unchanged from [SP_OCL] for serial (115200 ⇄ 921600 via `0x91`). On RFCOMM the speed state does
not exist: `supports_speed_change=false`, so the driver never enters the raise/restore path and
the link runs at whatever RFCOMM negotiates.

## 05. Verification Criteria  {#SP_BTT_05}

### 05_01. Functional Expectations  {#SP_BTT_05_01}

| Contract | Scenario | Input | Expected outcome |
|----------|----------|-------|------------------|
| Transport.read | Timeout, no data | `n=3`, nothing arriving | Returns `b""` (no raise); driver treats as stop |
| Transport.read | Partial then rest | fragmented delivery | Successive reads accumulate to full packet via `_read_exact` |
| Transport.write | Large packet | > RFCOMM MTU | All bytes delivered (send loop); no truncation |
| set_link_speed | On RFCOMM | any baud | No-op (never called; direct call → `UnsupportedCapability`) |
| build_transport | Serial auto | `SerialEndpoint(null)` | `auto_find_port` used; `DeviceNotFound` if none |
| build_transport | BT, no channel | `BluetoothEndpoint(addr, null)` | `resolve_spp_channel` runs; channel bound |
| DeviceService.connect | Legacy call | `connect("/dev/ttyUSB0", 115200)` | Identical to pre-change behaviour (serial path, speed-raise) |
| DeviceService.connect | BT happy path | `BluetoothEndpoint(addr)` | OBEX CONNECT succeeds; status connected; **no** speed-raise attempted |
| POST /api/connect | Legacy body | `{port, baud}` | Unchanged serial behaviour |
| POST /api/connect | BT body | `{transport:"bluetooth", address}` | Connects over RFCOMM |

### 05_02. Invariant Checks  {#SP_BTT_05_02}

| Invariant | Verification method |
|-----------|-------------------|
| OBEX framing unchanged | Byte-for-byte identical packets produced over serial before/after refactor (capture & compare) |
| `read` returns `b""` on timeout | Unit test with a fake transport that yields nothing within `read_timeout` |
| `write` is complete | Fake transport counts bytes; assert == input length across a chunked sink |
| Speed-raise skipped on BT | With a fake BT transport (`supports_speed_change=false`), `connect` performs no `set_link_speed` call |
| Serial path unregressed | Existing serial connect + acquire scripts pass unchanged |
| `open()` re-entry guarded | Call `open()` twice → `TransportError` |

### 05_03. Integration Scenarios  {#SP_BTT_05_03}

| Scenario | Preconditions | Steps | Expected result |
|----------|--------------|-------|-----------------|
| **Live OBEX-over-BT handshake** (closes [C_BTT_DEC_05]) | Oscill DSO powered, connectable, paired in OS | 1. `connect(BluetoothEndpoint("20:13:04:24:20:55"))` 2. read a version property (e.g. VSD) 3. acquire one frame | CONNECT→`0xA0`; property returns 4 ASCII bytes; frame parses to samples — proving the full path |
| End-to-end via web API | Backend running, scope connectable | `POST /api/connect {transport:"bluetooth", address:…}` then `GET` a frame | Frame served to the frontend over BT link |
| Fallback channel | Scope up, SDP unavailable | connect with `channel=null` | Warns, tries channel 1, connects |
| Serial regression | USB scope attached | Run existing acquisition script | fps/behaviour unchanged from pre-change baseline |

### 05_04. Edge Cases and Boundaries  {#SP_BTT_05_04}

| Case | Input | Expected behavior |
|------|-------|-------------------|
| Scope powered off (BT) | valid address | `BluetoothUnreachable`, clear message; no hang beyond connect timeout |
| Not paired | valid address, no OS bond | Connect refused → `BluetoothUnreachable` advising to pair first |
| Bad address format | `"20:13:04"` | Validation error before any I/O |
| Channel out of range | `channel=99` | Validation error |
| BT link drops mid-acquisition | connected, then out of range | `read`/`write` raise → acquisition self-heals (disconnect after N errors) |
| transport=bluetooth, no address anywhere | env unset, body empty | `ConfigError` naming `OSCILL_BT_ADDR` |

## 06. Reversibility  {#SP_BTT_06}

### 06_01. Rollback Strategy  {#SP_BTT_06_01}

| Aspect | Rollback approach |
|--------|-------------------|
| Data/state changes | None persisted. The endpoint/capabilities are in-memory value types; dropping them loses nothing. |
| Artifacts | Remove `transport.py` / `serial_transport.py` / `rfcomm_transport.py`, the `bluetooth` branch in the connect resolver, and the added API fields. |
| Dependent modules | SP_OCL (driver holds a transport), SP_DSV (connect superset), SP_WEB (ConnectReq fields). Reverting = restore the driver's `self.ser` and the `(port, baud)` connect; the serial transport *is* the original code path, so USB behaviour returns intact. |
| External contracts | `/api/connect` gains only **optional** fields; removing them restores the prior body. No breaking API change. `OSCILL_TRANSPORT`/`OSCILL_BT_*` env keys are additive; unset ⇒ serial. |

Minimum safe state: serial-only USB connectivity (the pre-feature behaviour), reached by deleting the RFCOMM transport and the bluetooth branch while keeping the serial transport.

## 07. Design Decisions  {#SP_BTT_DEC}

### DEC_01 — Connection input shape at the service/API layer  {#SP_BTT_DEC_01}

> **Status:** resolved
> **Date:** 2026-07-17

**Question:** How does a caller express *which link* to connect over, without breaking the existing `(port, baud)` / `{port, baud}` callers?

**Options considered:**
| Option | Consequence |
|--------|-------------|
| A — `ConnectionEndpoint` discriminated union + legacy `(port,baud)` shim | One canonical value type; legacy path maps to SerialEndpoint; API gains optional fields. Clean, backward-compatible. |
| B — Add loose kwargs (`transport`, `address`, `channel`) throughout | Fewer types, but scatters branching and lacks a single validated shape. |

**Decision:** A — `ConnectionEndpoint` union with a backward-compat shim.
**Rationale:** Gives one validated, immutable input to `build_transport`; keeps every current caller working; the API only *adds optional* fields (no breaking change).
**Rejected because:** B spreads the same branching the transport seam is meant to contain (echoes C_BTT_DEC_01 at the service layer).

### DEC_02 — SDP channel-resolution mechanism  {#SP_BTT_DEC_02}

> **Status:** open
> **Date:** 2026-07-17

**Question:** How is the SPP RFCOMM channel discovered on Linux, given the Python stdlib RFCOMM socket cannot perform SDP?

**Options considered:**
| Option | Consequence |
|--------|-------------|
| A — Shell out to a system tool (`sdptool browse` / `bluetoothctl`) and parse the SPP record | No new Python dependency; depends on an installed tool + device reachable for SDP. |
| B — Query BlueZ over D-Bus | No subprocess; adds a D-Bus dependency and more code. |
| C — Require an explicit channel (config/request), skip discovery | Simplest; pushes the channel onto the user. |

**Decision:** OPEN — the contract ([SP_BTT_02_07](#SP_BTT_02_07)) is fixed (explicit → SDP → fallback 1); the *mechanism* for the SDP step is chosen in the plan/implement phase.
**Rationale:** The resolution **contract** and its fallback chain are what other contracts bind to; the mechanism is fully isolated behind the `resolve_spp_channel` boundary (input BD_ADDR → output channel), so choosing A/B/C changes nothing outside that function. The safe fallback (explicit channel or channel 1) means the feature works even before the mechanism is finalized.
**Resolution trigger:** the implement phase for `resolve_spp_channel` — pick A/B/C when the live device is available to test SDP; if SDP proves unreliable, default to C.

### DEC_03 — No Bluetooth device auto-discovery in this version  {#SP_BTT_DEC_03}

> **Status:** resolved
> **Date:** 2026-07-17

**Question:** Should the backend discover the Oscill by scanning/name-match (like the Windows app), or require a configured address?

**Decision:** Require an explicit address (request field or `OSCILL_BT_ADDR`); no scan/name-match.
**Rationale:** The device is already paired and its address is known (`20:13:04:24:20:55`); requiring it keeps the feature minimal (no discovery contract, no name-match heuristic) and matches the "Python backend only / minimal" scope from [C_BTT_DEC_02]. Auto-discovery is a self-contained future addition if a real need appears.
**Rejected because:** name-based auto-discovery adds a discovery contract and UI with no current consumer (YAGNI).

### DEC_04 — `read` returns empty on timeout (never raises)  {#SP_BTT_DEC_04}

> **Status:** resolved
> **Date:** 2026-07-17

**Question:** What does `Transport.read` do when the read budget elapses with no/partial data?

**Decision:** Return the bytes received so far (possibly `b""`); never raise on timeout. Raise only on a genuine link error.
**Rationale:** This is the exact contract the existing SP_OCL `_read_exact`/`_read_resp` loop already relies on (serial `read` returns `b""` on timeout). Preserving it means the OBEX driver's read logic is untouched and behaves identically on RFCOMM (whose `socket.timeout` must be translated to an empty return).
**Rejected because:** raising on timeout would force rewriting every driver read site and change acquisition timing semantics.

## Changelog

| Date | Change |
|------|--------|
| 2026-07-17 | Initial draft — Transport abstraction (Serial + RFCOMM), ConnectionEndpoint model, SPP channel resolution, connect/API/config extensions; modifies SP_OCL (driver over transport), SP_DSV (connect superset), SP_WEB (ConnectReq fields). 4 design decisions (DEC_02 open → implement). |
| 2026-07-17 | Windows-app study (`firmware/oscill_new/`): device advertises **both** Object Push + Serial Port BT services → added dual-service caveat to SP_BTT_02_07 (SDP must target SPP; fallback-to-1 is best-effort/unverified). Confirmed WCL pairing flow (auto-PIN) — no device-side BT-enable exists; pairing is the host-side precondition already captured in the connect error table + edge cases. |
| 2026-07-17 | **Working-source confirmation** (old B4A Android app `OscillDroidApp`): validates the whole design — single OBEX driver dispatched to pluggable BT/USB transport (= DEC_01), SPP connect via UUID `00001101-…805F9B34FB` with SDP auto-channel + explicit-channel fallback (= SP_BTT_02_07), transport is a pure byte stream, no baud/speed over BT (= capability gating), device MAC persisted in config (= OSCILL_BT_ADDR), pre-paired-only + host-adapter-enable-only (no device enable). No spec change needed — design confirmed. |
| 2026-07-17 | **LIVE OBEX-over-BT PASS** (`scripts/test_bt_quick.py`, Oscill DSO 20:13:04:24:20:55): RFCOMM ch1 + OBEX CONNECT + props (VNM=Uosc, VSN=6070, VHW=1.25, VSW=1.26) + 252-sample frame. **New hard requirement added to §02_01: RFCOMM MUST use `BT_SECURITY_LOW` (insecure)** — default security stalls the device. Pairing (PIN 0000) is a precondition; SDP needs an active ACL. Closes C_BTT_DEC_05 + SP_BTT_DEC_02. |
