# Bluetooth Connectivity via Transport Abstraction  {#C_BTT}

> **Code:** C_BTT
> **Status:** active
> **Created:** 2026-07-17
> **Updated:** 2026-07-17
> **Author:** claude-opus-4-8
> **Owner:** Python backend module (`web_oscill`)
> **Complexity:** medium
>
> **Depends on:** [C_OCL](./oscill_client.concept.md), [C_DSV](./device_service.concept.md)
> **Used by:** [C_DSV](./device_service.concept.md), [C_WEB](./web_api.concept.md)
> **Spike:** —
> **Specification:** [SP_BTT](./bluetooth_transport.sp.md)
> **Plan:** [PL_BTT](./bluetooth_transport.plan.md)
>
> The Oscill oscilloscope speaks a **transport-neutral** OBEX protocol and advertises a
> Bluetooth Classic link alongside USB serial. Today the Python backend can only reach the
> device over USB (CP210x serial). This concept adds Bluetooth (RFCOMM/SPP) connectivity by
> extracting a **transport seam** in the OBEX driver: OBEX framing stays unchanged; the byte
> stream underneath becomes pluggable (USB serial *or* Bluetooth RFCOMM).

## 1. Philosophy  {#C_BTT_01}

### 1.1. Core Principle  {#C_BTT_01_01}

The Oscill device is an **OBEX server** that responds to the same request packets regardless
of the physical link carrying them — the protocol reference explicitly lists **RS232 / USB /
BT / IRDA** as interchangeable links ([project.md](./project.md), [protocol.md](./protocol/protocol.md)),
and the Android client already models this with an `ObexTransport` interface abstracting "TCP,
RFCOMM device file exposed by Bluetooth or USB, RFCOMM socket, Irda".

The Python backend, however, hard-couples the OBEX driver to `pyserial` (`self.ser`). Bluetooth
support therefore is **not a protocol change** — it is a **transport change**. The problem this
concept solves: let a user connect the PC software to the oscilloscope wirelessly over the
Bluetooth radio already present on the machine, without duplicating the OBEX framing logic or
disturbing the existing USB path.

**Why now:** the target unit ships a Bluetooth Classic module (verified: the device
`Oscill DSO`, BD_ADDR `20:13:04:24:20:55`, is discoverable from this machine as a Bluetooth
Classic / legacy-pairing peripheral), and the host has a working Bluetooth 5.3 radio. The
only missing piece is the software link.

**Prior art (verified reference implementation).** The vendor's Windows application
(`firmware/oscill_new/`) already implements Bluetooth exactly this way, which de-risks the
design:

- The link-selection UI (`oscilink.lng`) offers **"Bluetooth COM-port / oscill"** alongside USB
  and **"COM/VCP"** — Bluetooth is presented as a serial link to the user.
- `wcl.dll` (Wireless Communication Library over the Widcomm/Broadcom stack) uses
  `BT_SearchSPPExServices` → `Btsdk_GetAvailableExtSPPCOMPort` → `WD_CreateRfCommClient` /
  `BT_ConnectSPPExService` with a resolved RFCOMM **Channel** — i.e. the device exposes the
  standard **Serial Port Profile (SPP) over RFCOMM**; the channel is discovered, not hardcoded.
- `TestBT.exe` (a registered COM helper) discovers the device by address (`OscillAddr`).
- `oscilink.dll`'s job is described in its own type library as *"Open COMport or USB device and
  send OBEX Connect"* — **one OBEX layer over either link**, which is precisely the transport
  seam this concept introduces.

Confirmed facts from this reference: Bluetooth link = **SPP/RFCOMM**, OBEX is **identical** to
USB, channel is **resolved dynamically** (SDP), and pairing is handled by the OS/stack (no PIN
hardcoded in the app).

### 1.2. Design Constraints  {#C_BTT_01_02}

- **OBEX framing is untouched.** Packet building/parsing, register/property/command headers,
  connection-ID handling, Continue/Abort flow, and checksum logic stay exactly as they are.
  This concept only changes *where the bytes come from and go to*.
- **The USB path must not regress.** The existing serial connection (auto-detect, handshake,
  speed-raise to 921600, frame-wait cache) remains the default and behaves identically.
- **Transport-specific capabilities are isolated behind the seam.** Baud rate and the `0x91`
  speed-raise are **serial-only** notions; over RFCOMM the link throughput is negotiated below
  OBEX and baud is meaningless. Such capabilities live inside the serial transport, never in
  the OBEX driver or in the Bluetooth transport.
- **Layering preserved** ([`LayerDependencyDirection`](../.dev_flow/rules/architecture.md),
  [`HardwareAccessOnlyThroughDeviceService`](../.dev_flow/rules/architecture.md)): the transport
  is Layer 0 (peer of / below the OBEX driver); all hardware access still flows web → DeviceService
  → OscillClient → Transport. The web layer never touches a transport.
- **No new heavy dependency.** Bluetooth RFCOMM is reachable from the Python standard library
  (`socket.AF_BLUETOOTH` / `BTPROTO_RFCOMM`, verified available on the target interpreter) — no
  `pybluez` build required. Pairing/OS-level bonding is handled by the operating system's
  Bluetooth stack (BlueZ), outside this software.
- **Rollback:** the transport seam is additive. Reverting = deleting the Bluetooth transport
  and the transport-selection branch; the serial transport is the original code path, so the
  system returns to USB-only with no data-model change.
- **Scope decision:** this concept covers the **Python backend only** (see [C_BTT_DEC_02](#C_BTT_DEC_02)).
  The web frontend inherits Bluetooth for free through the existing HTTP API (a connection is a
  connection). The Android app is out of scope.

**This concept IS:** a transport abstraction in the Python OBEX driver + a Bluetooth RFCOMM
transport + the connection-request plumbing to choose a link.

**This concept IS NOT:** an OBEX protocol change, a Bluetooth pairing/bonding manager, a device
discovery UI, a BLE (GATT) implementation, or an Android change.

## 2. Domain Model  {#C_BTT_02}

### 2.1. Key Entities  {#C_BTT_02_01}

| Entity | Responsibility |
|--------|----------------|
| **Transport** | Abstract byte-stream link to the device: establish, tear down, read, write, and flush/reset the stream. Hides *how* bytes travel. |
| **Serial Transport** | Transport backed by USB serial (CP210x via `pyserial`). Owns baud rate, the `0x91` speed-raise, and port auto-detection — all serial-only concerns. |
| **Bluetooth (RFCOMM) Transport** | Transport backed by a Bluetooth Classic RFCOMM socket to a device address + channel. Owns RFCOMM channel resolution (SDP/SPP) and socket lifecycle. |
| **Endpoint** | The address a transport needs: for serial = port path + baud; for Bluetooth = BD_ADDR + RFCOMM channel. |
| **OBEX Driver** (existing `OscillClient`) | Speaks OBEX over *a* Transport. No longer knows whether the link is USB or Bluetooth. |

```
        DeviceService  (Layer 1, singleton, serialized access)
              │  connect(endpoint)
              ▼
        OBEX Driver  (Layer 0 — OBEX framing only)
              │  read()/write()/reset()
              ▼
     ┌──────────────── Transport (abstract) ────────────────┐
     │                                                       │
 Serial Transport                               Bluetooth (RFCOMM) Transport
 (pyserial, baud, 0x91)                         (AF_BLUETOOTH socket, SDP/SPP)
     │                                                       │
 /dev/ttyUSB* (CP210x)                          BD_ADDR:channel  (Oscill DSO)
```

### 2.2. Data Flows  {#C_BTT_02_02}

**Connect (Bluetooth):** a connection request carries a *transport kind = bluetooth* and an
endpoint (device address, optional channel). DeviceService constructs the OBEX driver over a
Bluetooth transport → transport opens an RFCOMM socket to the device (channel resolved by SDP
lookup of the SPP service, or taken from the request) → OBEX `CONNECT` handshake proceeds
**identically** to USB → device replies `0xA0`, connection ID stored.

**Acquire / configure:** unchanged. Register writes, the `D`/`C` commands, and frame reads all
run through the same OBEX driver; each `read`/`write` lands on the active transport. The
frame-wait cache and timing formulas are byte-count driven and transport-neutral.

**Speed control:** on USB the driver may raise baud after init (`0x91`); on Bluetooth this step
is a **no-op** — the transport reports "speed control not applicable", so the driver simply
skips it. RFCOMM throughput is what the link negotiates.

## 3. Mechanisms  {#C_BTT_03}

### 3.1. Core Algorithm  {#C_BTT_03_01}

**Transport seam.** The OBEX driver holds a Transport (not a serial handle). Everywhere it
currently reads/writes serial bytes or flushes buffers, it calls the transport's read / write /
reset. `open`/`close` delegate to the transport. This is a behaviour-preserving extraction for
the USB path.

**Transport selection.** The connect entry point accepts a transport kind + endpoint. Absent an
explicit kind, the existing port/baud form selects the serial transport — preserving every
current caller and the auto-detect default. A Bluetooth kind selects the RFCOMM transport with a
device address (and optional channel).

**RFCOMM channel resolution.** A Bluetooth SPP service is reachable on an RFCOMM *channel*
number. The transport resolves it by querying the device's service records (SDP) for the
Serial-Port service (UUID `0x1101`); if the request already carries a channel, that is used
directly. This mirrors the Windows reference, which searches the SPP service and takes the
resolved channel rather than assuming one. (Many SPP devices expose channel 1; SDP resolution
avoids hard-coding.)

**Capability isolation.** Serial-only operations (baud raise, buffer reset semantics) are
expressed as transport capabilities. The driver asks the transport "can you change speed?"
rather than assuming a UART. The Bluetooth transport answers no; the serial transport answers
yes and performs the `0x91` exchange.

### 3.2. Edge Cases  {#C_BTT_03_02}

| Scenario | Behaviour |
|----------|-----------|
| Device powered off / not connectable | RFCOMM connect fails fast (OS "Host is down"); surfaced as a clear "device not reachable over Bluetooth" connect error, mirroring the serial "Device not found". |
| Not paired / bonding required | Pairing is the OS's responsibility (BlueZ). If the socket connect is refused for auth, the error message directs the user to pair the device first. |
| RFCOMM channel not found via SDP | Fall back to the request-supplied channel; if none, report an actionable error naming the SPP-lookup failure. |
| Mid-stream Bluetooth link drop | Read/write raises; handled by the existing acquisition self-healing (disconnect after N consecutive errors — [`AcquisitionLoopSelfHealingDisconnect`](../.dev_flow/rules/error-handling.md)). |
| Higher / variable latency vs USB | Timing is byte-count driven; the frame-wait cap already bounds waits. Bluetooth is slower than 921600-baud USB but functionally correct. |
| Speed-raise requested on Bluetooth | Silently skipped (capability = unsupported); not an error. |

## 4. Integration Points  {#C_BTT_04}

### 4.1. Dependencies  {#C_BTT_04_01}

- **[C_OCL] OBEX Device Driver** — refactored to own a Transport instead of a raw serial handle.
  This is the primary touch point; OBEX logic is otherwise unchanged.
- **[C_DSV] Device Service** — the connect path constructs the driver; it must accept and pass a
  transport kind + endpoint (defaulting to serial for backward compatibility).
- **[C_WEB] Web API** — the connect request/endpoint may carry a transport choice so the user can
  pick Bluetooth; otherwise inherits the default. Web frontend needs no protocol change.
- **Operating system Bluetooth stack (BlueZ)** — owns discovery, pairing, and bonding. This
  software connects to an already-pairable device; it does not manage bonds.
- **Python standard library** `socket` (`AF_BLUETOOTH`, `BTPROTO_RFCOMM`) — the RFCOMM link.

### 4.2. API Surface  {#C_BTT_04_02}

- **Transport contract** (abstract): open, close, read(n), write(bytes), reset/flush, and a
  capability query (e.g. supports-speed-change). Consumed only by the OBEX driver.
- **Connect contract** (extended): the existing connect gains an optional transport kind +
  endpoint; the serial form remains the default. Exposed upward through DeviceService and,
  optionally, the web connect endpoint.
- **Configuration surface**: environment/config keys to select the default transport and Bluetooth
  endpoint (e.g. a transport selector, a device address, an optional channel), consistent with the
  existing `OSCILL_*` env convention. Exact keys defined in the spec.

## 5. Design Decisions  {#C_BTT_DEC}

### DEC_01 — Transport seam vs. parameterized client  {#C_BTT_DEC_01}

> **Status:** resolved
> **Date:** 2026-07-17

**Question:** How should the byte-stream transport relate to the OBEX framing in the Python client?

**Options considered:**
| Option | Consequence |
|--------|-------------|
| A — Introduce a Transport abstraction (serial + RFCOMM behind one interface) | Clean separation; USB-only concerns (baud, `0x91`) isolated; testable with a fake transport; mirrors the Android `ObexTransport` design. Requires a behaviour-preserving refactor of the driver's serial calls. |
| B — Parameterize `OscillClient` to accept serial *or* RFCOMM, branching internally | Less refactoring up front; but couples USB and BT concerns, scatters `if bluetooth` branches, and leaves baud/speed logic mixed into the driver. |

**Decision:** A — Transport abstraction.
**Rationale:** Matches the protocol's transport-neutral nature and the existing Android model; keeps OBEX framing single-sourced; contains serial-only logic; makes the driver unit-testable without hardware.
**Rejected because:** B accrues branching debt in the hottest code path and re-mixes exactly the concerns this feature needs separated.

### DEC_02 — Scope: Python backend only  {#C_BTT_DEC_02}

> **Status:** resolved
> **Date:** 2026-07-17

**Question:** Which client(s) receive Bluetooth support in this concept?

**Options considered:**
| Option | Consequence |
|--------|-------------|
| A — Python backend only | The PC software under test on this machine gains BT; web frontend inherits it via HTTP; single codebase. |
| B — Python + Android | Two codebases; Android's `ObexTransport` would need a concrete BT implementation. |
| C — All three + frontend transport UX | Widest scope, largest surface. |

**Decision:** A — Python backend only.
**Rationale:** "ПО" (the software) on this computer is the Python backend + web UI; the live Bluetooth radio being validated is this host's. Web frontend benefits automatically. Keeps the change focused and reversible.
**Rejected because:** B/C widen scope beyond the stated goal; Android BT can be a later, separate concept if needed.

### DEC_03 — RFCOMM via stdlib socket vs. `/dev/rfcomm` bind  {#C_BTT_DEC_03}

> **Status:** resolved
> **Date:** 2026-07-17

**Question:** How does the Bluetooth transport obtain its byte stream on Linux?

**Options considered:**
| Option | Consequence |
|--------|-------------|
| A — Direct `socket.AF_BLUETOOTH` / `BTPROTO_RFCOMM` connect to (BD_ADDR, channel) | No root, no external `rfcomm bind`, no extra dependency; stream lives in-process. Not `pyserial`, so serial-only calls must already be behind the transport seam (they are, per DEC_01). |
| B — `rfcomm bind /dev/rfcomm0` then open with `pyserial` | Reuses the serial code path verbatim, but needs a privileged bind step outside the app and an external device node — brittle, root-requiring, extra operational surface. |

**Decision:** A — direct RFCOMM socket via the standard library.
**Rationale:** Self-contained, unprivileged, no new dependency (verified: `AF_BLUETOOTH`/`BTPROTO_RFCOMM` present); the transport seam already isolates serial-only behaviour, so a socket-backed stream fits cleanly. The Windows reference uses the equivalent-but-heavier VCP model (Widcomm `Btsdk_GetAvailableExtSPPCOMPort` → open as a COM port), which **proves the SPP-as-serial path works**; Option A is the Linux-native, unprivileged form of the same idea.
**Rejected because:** B pushes setup outside the software, requires root, and adds a fragile `/dev/rfcomm0` lifecycle. (It remains a proven fallback if a direct socket ever misbehaves, since it is what Windows effectively does.)

### DEC_04 — Serial speed-raise (`0x91`) over Bluetooth  {#C_BTT_DEC_04}

> **Status:** resolved
> **Date:** 2026-07-17

**Question:** What happens to the baud speed-raise on the Bluetooth link?

**Decision:** It is a **no-op** on Bluetooth, expressed as a transport capability (serial supports speed change; RFCOMM does not).
**Rationale:** RFCOMM throughput is negotiated below OBEX; baud has no meaning. The driver queries the capability instead of assuming a UART, so the step is skipped cleanly rather than erroring.

### DEC_05 — Live end-to-end handshake verification  {#C_BTT_DEC_05}

> **Status:** resolved
> **Date:** 2026-07-17

**Question:** When is the full OBEX-over-Bluetooth handshake proven on real hardware?

**Decision:** RESOLVED — **live PASS 2026-07-17.** `scripts/test_bt_quick.py` connected the
`Oscill DSO` over RFCOMM (ch1, insecure), completed OBEX `CONNECT`, read properties
(VNM=Uosc, VSN=6070, VHW=1.25, VSW=1.26), and acquired a 252-sample frame.
**Rationale:** The design is now hardware-proven end-to-end. Required recipe captured in
skill `oscill_bluetooth_transport` and SP_BTT §02_01: reset host adapter after the VirtualBox VM
releases the dongle; OS-pair (PIN 0000); RFCOMM with `BT_SECURITY_LOW` (insecure); SPP on ch1.
**Resolution trigger:** — (closed; end-to-end via `/api/connect` re-checked in Verify once the
service-layer phases land).

## Changelog

| Date | Change |
|------|--------|
| 2026-07-17 | Initial draft — Bluetooth (RFCOMM/SPP) connectivity via a transport abstraction in the Python OBEX driver. Live handshake deferred to Verify (DEC_05). |
| 2026-07-17 | Corroborated against the vendor Windows app (`firmware/oscill_new/`): confirmed BT link = SPP/RFCOMM (WCL/Widcomm `BT_*SPP*`/`WD_*RfComm*`), dynamic SDP channel resolution, OBEX identical over either link, OS-handled pairing. Added prior-art section; refined §3.1 (SPP UUID 0x1101) and DEC_03 (VCP as proven fallback). |
