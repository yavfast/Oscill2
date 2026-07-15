# Spike: Firmware Update Method & Modification Feasibility

Status: draft (investigation — no pipeline gates)
Date: 2026-07-14
Goal: determine how the Windows software updates firmware, and whether the 1.26 defects
(`firmware_1.26_defects.md`) can be fixed on the owner's own device.
Sources: decompressed `oscill.exe` + `oscilink.dll` (UPX-unpacked from `oscilnew.zip`),
official firmware pages, live device (`/dev/ttyUSB0`), `web_oscill/oscill_client.py`.

## 1. Firmware architecture (confirmed, vendor docs)
The MCU flash holds **two parts**:
- **Bootloader** — permanent. Stores serial, bootloader version, device-name code (`uosc`),
  platform code `X.YZ`. *"Rewriting the bootloader during operation is impossible — only by
  connecting a special programmer to the board … exclusively by the manufacturer."*
  *"Without the bootloader, writing firmware to the oscilloscope is impossible."*
- **Working application** — the updatable part. Handles digitizing, analog control, PC comms.
  Updated by **winoscill** over the normal UART/USB link, without touching the bootloader.

## 2. Update method (the `.ofw` path) — how winoscill flashes
Reconstructed from `oscill.exe` strings + `oscilink.dll` API + vendor procedure:

1. User: **File → Firmware update**, pick `*.ofw`. App parses the **plaintext header**
   (`Target: Uosc`, `Version: 1.26`, `Date:`, then `FW:` + payload).
2. App validates compatibility: `Target:` vs device `VNM` (`Uosc`) and revision — else
   *"Firmware uncompatible!"* / *"Firmware file error!"*.
3. App commands the device into **BOOT** state (resident bootloader): *"Device state: BOOT /
   Need to upload firmware. Process?"*.
4. App streams the payload to the bootloader **sector by sector** over OBEX, checking each
   (`FirmWareUpdateStart` → per-sector `FirmwareSectorUpdateRezult` → done). Transport is the
   same OBEX link used for normal operation — `oscilink.dll` = *"Oscill OBEX & link library"*,
   riding **CP210x_\*** + **SI_\*** (USBXpress `SiUSBXp.dll`) for USB, **WCL** for Bluetooth.
   Packet size bounded by `MaxOBEXpacketSize` (relevant to defect D-03).
5. On success the app confirms; failure → *"Firmware update failed. Reconnect oscill and repeat"*.
6. Verify via **Menu → Device → Version** (`VSW`).

Key point: this is **application-layer** flashing through a resident bootloader — **no Silicon
Labs factory tool needed** to update the working part. The Android app has **no** FW-update code;
only winoscill can flash.

## 3. RESOLVED (Ghidra, 2026-07-14): Hypothesis **B** — bootloader decrypts
Static RE of `oscill.exe` (native VB6) settled §3-old decisively (confidence: high).
Full dumps: scratchpad `decomp_exe.txt`, `FINDINGS_map.txt`, `FwDump.java`; Ghidra projects
`ghproj_exe/` retained.

- The `.ofw` loader `FUN_005b2b40` reads the whole file into a VB string, `InStr`-parses the
  plaintext header (`Target: `/`Version: `/`Date:`/`FW:`), and copies the bytes after `FW:`
  **verbatim** — **no XOR/add/table/LFSR/crypto/decompress anywhere** in the path. No key/constant
  array exists in the exe because none is needed. → **The exe sends the payload still-encrypted; the
  device bootloader decrypts internally.** The easy "extract the key from the PC app" route is dead.
- **Sector geometry (arithmetically exact):** `numSectors = len >> 9` (÷512), `sectorSize = len /
  numSectors`, reject if not divisible → `Firmware file error!`. For `Uosc126.ofw`: payload 30840 B =
  **60 sectors × 514 B**. Each 514 B = one **512 B C8051F34x flash page + 2 B** → strong
  corroboration of the C8051F34x family (512 B page size). The 2 extra bytes are part of the
  pre-built encrypted image (bootloader-checked), **not** a PC-computed CRC (the exe computes none).
- **Framing** (`FUN_005b3720`): 60×514 B slices sent as OBEX **PUT** packets (name+value headers,
  `MaxOBEXpacketSize`) via `oscilink.dll` COM `ClassOBEX` over CP210x/USBXpress or WCL Bluetooth.
  Sector label first char: `"E"` = last/end, `"O"`, else numeric index.
- **Compatibility** (`FUN_005b3e00`): reads device identity over COM, `__vbaStrCmp` of header
  `Target:` vs device name + version/revision → `Firmware uncompatible!` on mismatch.
- **BOOT entry** (`FUN_004fac80`): app *detects* `"BOOT"` state by string compare; the reboot-into-
  bootloader trigger is a device COM method (candidate vtable[0xdc0]) — exact opcode not pinned.

### Consequence for modification
The decryption key/algorithm live **only in the bootloader**, which is not readable from the PC
side and (per vendor) rewritable "only by the manufacturer". So the `.ofw` route cannot be used to
inject modified code **unless we obtain plaintext by another means** (§4) and can reproduce the
per-page cipher. The keystream is position-fixed and **shared across versions** (§6a), so recovering
it once (from any plaintext/ciphertext pair) unlocks crafting arbitrary valid `.ofw` images.

<details><summary>Superseded §3 (the dynamic A/B experiment — no longer needed)</summary>
- Payload entropy ≈ 7.98 bits/byte → encrypted (or compressed+encrypted); not raw 8051 code.
- `oscill.exe` contains a `FWupdateKey` symbol → the app holds a key. **Two hypotheses**, with
  very different consequences for modification:

  **(A) App decrypts, sends plaintext sectors; bootloader writes verbatim.**
  → The *plaintext* firmware is observable on the wire (or by hooking `SI_Write`/`WriteFile`).
  No cipher needs breaking: capture once → get a readable image; craft our own sector uploads.

  **(B) App sends the encrypted payload; bootloader decrypts internally.**
  → Key/algorithm live in the (unreadable) bootloader. Modification requires either breaking the
  cipher from `oscill.exe` (if it also encrypts) or the C2 route (§5).

- **Discriminating test (cheap, non-destructive):** run a real update once and compare the bytes
  put on the wire against the `.ofw` payload:
  - bytes ≈ `.ofw` payload → **hypothesis B**;
  - bytes differ and look like 8051 opcodes (recognizable vectors/`LJMP` at 0x0000, sparse 0xFF
    fill) → **hypothesis A** → we already have the plaintext.
  - How to capture on Linux: run `oscill.exe` under **Wine** bound to `/dev/ttyUSB0`, and sniff
    with a serial tee / `strace -e write` on the Wine process, or interpose the OBEX PUT bodies
    using the existing `web_oscill/oscill_client.py` framing (`OSCILL_DATA` header) as a decoder.
  - Safer variant that risks no flash write: capture the **first** sector burst then abort
    (`OBEX_ABORT`) before commit — enough to classify A vs B.

</details>

## 4. Revised strategy after the Hypothesis-B verdict

The order of preference **flips**. Getting readable code now hinges on **C2 hardware**, not the PC app.

### Path A — C2 flash readout  *(now the pivotal experiment)*
Attach a Silicon Labs C2 debug adapter (§5) and attempt to **read** the C8051F34x flash.
- **If readback is NOT locked** → dump the live **1.26** image = plaintext. Then everything opens:
  - `dump XOR Uosc126.ofw-payload` (page-aligned) **recovers the position-fixed keystream** → we can
    encrypt/decrypt any image and build valid `.ofw` files the stock bootloader accepts.
  - Patch D-01 in the dumped code and re-flash **either** via C2 (whole image, bypass bootloader
    crypto) **or** via a crafted `.ofw` through the untouched bootloader (safer, recoverable).
- **If readback IS locked** (flash security byte set) → C2 can still **mass-erase + write** custom
  code, but that **wipes the bootloader** (unrecoverable — vendor-only), so only do that for
  fully-custom firmware you accept losing the stock app for. Prefer Path B first.

### Path B — ciphertext-only cryptanalysis of the `.ofw` — **ATTEMPTED 2026-07-14, DID NOT BREAK**
> **Superseded reasoning — see §9.** The practical verdict (file-only recovery insufficient) stands,
> but the mechanism is now known: additive period-514 reused keystream, **not** compression. The
> "compressed before encryption" conclusion below was an artifact of the duplicate pages.
Analysis on `Uosc125.ofw` + `Uosc126.ofw` (scratchpad scripts). Findings:
- **Structure:** payload 30840 B = 60 pages × 514 B (512 B flash page + 2 B). A **position-dependent
  additive-type cipher with a per-position key of period 514** genuinely exists and is **shared
  across versions**: same-position cross-page coincidence 1.36% vs 0.39% random (>3×); mode-based
  recovery lowers image entropy 7.98 → 7.26 with a real 0x00 peak.
- **Why it did NOT fully break (ciphertext-only):** the plaintext pages are diverse and moderately
  high-entropy — pairwise page XOR `P[s]⊕P[t]` gives only ~0.4% zeros (near random), unlike plain
  8051 code (which would peak ~3–8% at 0x00). This strongly suggests the working part is
  **compressed before encryption**. Consequently per-column statistics over 60–120 samples do not
  pin each key byte; mode/EM recovery leaves non-canonical residue (0x92/0x28 artefacts) and yields
  **no readable code or strings**.
- **The padding crib failed:** pages that looked like constant fill are actually **duplicated real
  data pages** (pages {6,8,9,10,12,14,15,19,20,22,24,27,28} share ≥97–100% bytes). Their common
  content is high-entropy, not a constant, so it equals `P_common ⊕ K`, not `K`. These duplicates
  are also what produced the misleading period-514 autocorrelation peak (8.5%).
- **No 8051 vector table / ASCII cribs are exposed** (consistent with compression-under-encryption),
  so the classic known-plaintext lever is unavailable from the file alone.
- **Verdict:** ciphertext-only recovery is **insufficient**. Breaking it needs **one known-plaintext
  page** — a **C2 flash dump of any page (Path A)**. With the shared per-position key, one plaintext
  page recovers `K` for all positions; if a decompression stage exists it must then be reversed too.
  Scripts/artifacts retained in scratchpad (`dec*.bin`, `em_*.bin`, keystream candidates) for reuse
  once a crib is available.

### Path C — clean-room custom firmware via C2
Write new firmware from scratch (Keil C51 / SDCC), flash via C2. Full control, but you reimplement
the analog/ADC/OBEX stack and lose the stock bootloader — largest effort, last resort.

**Recommended (updated after Path B failed):** ciphertext-only cryptanalysis (Path B) has been
exhausted without a break — the file yields no crib. The path forward now **requires a C2 debug
adapter (Path A)**: dump any one flash page → known plaintext → recover the shared per-position key
→ decrypt everything (and reverse any decompression). Reading the C8051F34x device ID at the same
time settles the exact sub-part. Keep `Uosc125.ofw` / `Uosc126.ofw` as recovery images before any
write. If acquiring hardware is not desired, D-01 cannot currently be fixed by firmware patching.

## 4b. (historical) Path 1 — patch via the bootloader (`.ofw`), non-destructive
Prerequisites: readable working image (from §3-A capture, or §5 C2 read if unprotected) and the
ability to produce an image the bootloader accepts.
1. Obtain plaintext of **1.25 and 1.26** working code; **diff** to localize D-01 (roll/timebase).
2. Patch the 8051 code (disassemble with **naken_asm**; the core is a Silicon Labs
   C8051F34x — 8051 instruction set). Fix the roll-frame offset reset.
3. Re-package: match the sector framing + any per-sector/image **CRC** the bootloader checks
   (`Firmware file error!`/`Device firmware error` are the reject paths to satisfy). Under
   hypothesis A this is *plaintext sectors* — no re-encryption needed; under B, re-encryption.
4. Flash with winoscill **or** a home-grown updater built on `oscill_client.py` (we already speak
   OBEX to the device on `/dev/ttyUSB0`). The bootloader stays untouched → a bad flash is
   recoverable by re-entering BOOT and re-flashing a known-good `.ofw` (1.25/1.26).

Risk: low-moderate. The bootloader is the safety net; worst case re-flash stock 1.26.

## 5. Path 2 — Silicon Labs C2 programmer (fallback / full control)
Direct flash access via the on-board **C2 debug header** (`C2Dat`, C2CK=`-RES`, `+3V3`, `GND` —
see `firmware_hardware.spike.md`).
- **Hardware:** Silicon Labs **USB Debug Adapter (EC2/EC3/U-EC6)** or a **ToolStick** — still
  required; there is no no-hardware C2 path.
- **Open-source toolchain** (ref: github.com/cjacker/opensource-toolchain-8051):
  - **ec2-new** (github.com/paragonRobotics/ec2-new) — drives the USB Debug Adapter / ToolStick to
    **read/write C8051F flash over C2** (the open flasher; replaces the earlier "c2tool" note).
  - **naken_asm** — 8051 **assembler + disassembler** (fills the gap: capstone has no 8051 core;
    use it to disassemble a decrypted/dumped page for the D-01 patch).
  - **SDCC** — C compiler for authoring the patch / custom firmware; **newcdb** + **ucsim-51** for
    debug/simulation before flashing.
  - Official alternative: **flash8051** / Simplicity Studio + Flash Programming Utility (Keil C51 as
    the proprietary compiler option).
- **Can do:** read the exact **C8051F34x device ID** (settles the sub-part), erase + write arbitrary
  flash, un-brick.
- **Cannot / caveats:** if the **flash security byte** locks readback, C2 *read* of existing code is
  blocked; a **mass erase** unlocks but **wipes the bootloader too** — and the bootloader can only
  be restored "by the manufacturer" (its image is not published). So C2 is best for *un-bricking*
  or writing fully custom firmware, **not** for preserving the stock bootloader while reading the
  original app. Prefer Path 1 unless C2 read turns out to be unprotected.

## 6. Recommended sequence
1. Run the §3 discriminating capture (classify A/B; ideally harvest plaintext 1.26 + 1.25).
2. If plaintext obtained → **diff 1.25↔1.26**, locate D-01, patch, re-flash via bootloader (Path 1).
3. Keep `Uosc126.ofw` (+ fetch `fw_u125.zip`) as recovery images before any write.
4. Reserve C2 (Path 2) for device-ID confirmation and un-bricking only.

## 6a. Ciphertext-diff of 1.25 vs 1.26 (done 2026-07-14) — inconclusive
Fetched `fw_u125.zip` → `Uosc125.ofw`. Both images are **exactly 30928 bytes**; headers differ only
in Version/Date. Byte-comparison of the encrypted payloads:
- **90.8% of bytes differ** (28097 / 30928), spread across ~6 large regions spanning 0x42–0x78cf.
- There ARE aligned matching islands (~9%, vs ~0.4% expected by chance) → the cipher uses a
  **shared, position-fixed keystream** (likely a positional XOR/table), NOT compression
  (compression would misalign everything after the first change → ~0 aligned matches) and NOT a
  per-version keystream (that would erase the aligned matches).
- Yet ~91% differing is expected even for a minor rev: on 8051 a recompile shifts nearly all
  absolute `LJMP`/`LCALL` targets and data pointers, so most bytes change even where logic is same.
- **Consequence:** a raw `.ofw` byte-diff CANNOT localize D-01. We need **plaintext + a semantic
  diff of the disassembly** — which requires the decryption (the Ghidra RE task). This also implies
  `C125 XOR C126` cancels the keystream and yields `P125 XOR P126` directly — a lever for verifying
  the keystream hypothesis once plaintext of either version is known.
- Kept `Uosc125.ofw` and `Uosc126.ofw` as recovery/reference images (in scratchpad).

## 7. Open points / risks
- A vs B unresolved until the §3 capture is run (needs Wine + a live update, on the owner's device).
- Bootloader's acceptance checks (CRC/signature) not yet characterized — a signature (not just CRC)
  would block Path 1 re-packaging and force Path 2.
- Exact C8051F34x sub-part still unconfirmed (needs C2 device-ID read).
- Legal/ethical: own device, discontinued product, repair/interoperability purpose — fine; do not
  redistribute the vendor's firmware images or extracted key.

## 7a. Exact unpack & update algorithm (from decompilation)

**Boundary:** the PC-side container-unpack and the transfer protocol are fully recovered; the actual
crypto *unpacking* (decrypt + probable decompress) runs **inside the bootloader** and is NOT in the
PC files — see Part 3.

### Part 1 — PC-side container unpack (`FUN_005b2b40`, exact)
```
open(file, binary); buf = readWholeFile()
target  = Mid$(buf, InStr(buf,"Target: ")+8  .. CRLF)     # "Uosc"
version = Mid$(buf, InStr(buf,"Version: ")+9 .. CRLF)     # "1.26"
date    = Mid$(buf, InStr(buf,"Date:")+5     .. CRLF)     # "15032010" (DDMMYYYY)
payload = Mid$(buf, InStr(buf,"FW:")+3 .. end)            # raw, VERBATIM (no transform)
L = Len(payload)                                          # 30840
numSectors = L >> 9            # = L\512 (integer)  -> 60
sectorSize = L \ numSectors    # -> 514   (NB: derived, = 512-page + 2)
if (L mod sectorSize) != 0 : error "Firmware file error!"   # divisibility guard
```
No decryption/decompression here. `payload` stays encrypted (7.98 bit/byte).

### Part 2 — update transfer (PC → device)
1. **Compat** (`FUN_005b3e00`): read device identity props; `StrCmp` header `Target`/version/revision
   vs device → mismatch ⇒ `"Firmware uncompatible!"`.
2. **Enter BOOT** (`FUN_004fac80`): read device state; if ≠ `"BOOT"` invoke the reboot-to-bootloader
   device method, then confirm `"Device state: BOOT" / "Need to upload firmware. Process?"`.
3. **FirmWareUpdateStart(numSectors, sectorSize)** — device method (loader vtable[0xac]).
4. **Sector loop** i = 0..numSectors-1 (`FUN_005b3720`): `sector = Mid$(payload, i*514+1, 514)`;
   label the **last** sector `"E"` (end), others by numeric index (an `"O"` branch also exists),
   else `"Undefined sector ="`; send each as an **OBEX PUT_FINAL** packet via `oscilink.dll`
   `ClassOBEX` over CP210x/USBXpress (or WCL Bluetooth), bounded by `MaxOBEXpacketSize`; await the
   per-sector ack `FirmwareSectorUpdateRezult`; a `Timer/DoEvents` delay paces the loop.
   - OBEX PUT framing (per `web_oscill/oscill_client.py`): `0x82` opcode, 2-byte length, then
     `CONNECTION_ID(0xCB)+id` and a byte-sequence header carrying name + the 514-byte value.
5. **Finish**: success dialog; device resets into the new image; verify `VSW`. Any failure ⇒
   `"Firmware update failed. Reconnect oscill and repeat."` (device left in BOOT, safe to retry).

### Part 3 — on-device unpack (decrypt + decompress + flash) — **NOT DETERMINABLE from PC files**
> **Updated by §9.** The *decrypt* is now determined from the files alone — additive period-514
> reused keystream `C=(P+KS)%256` — and there is **no decompress stage** (the plaintext is not
> compressed). Only the keystream `KS` value and the 2-byte-field/flash-write remain bootloader-side.
The real "розпаковка" happens in the bootloader on the C8051F34x and is not present in `oscill.exe`,
`oscilink.dll`, or the `.ofw`. What we *do* know about it (from §3/§6a/Part 1): each 514 B sector =
one 512 B flash page + 2 B checked by the bootloader (not PC-computed); the transform is a
position-dependent additive-type cipher (per-position component, shared across versions) applied
over data that is itself high-entropy (⇒ likely compressed before encryption). Recovering the exact
decrypt/decompress requires **dumping the bootloader** (C2 read, or glitch bypass if locked — §8).

## 8. References — standard C8051F34x bootloader & C2 examples (found 2026-07-14)
The vendor bootloader is almost certainly derived from / mirrors the Silicon Labs reference design
(packet-based, UART **and** USB, resides in low flash + last page, cannot self-overwrite — matches
the vendor's own description). These give a concrete model of its layout & protocol:
- **AN778 "UART Bootloader"** (+ AN778SW source, Keil): bootloader at **0x0000–0x0400 + last flash
  page**, application starts at **0x0400**. Best structural match; explains why the `.ofw` image
  does not begin with a reset vector at offset 0.
  https://www.silabs.com/documents/public/application-notes/AN778.pdf
- **AN763 "UART and USB Bootloader Implementations"** — packet protocol + DFU state machine (the
  `.ofw` sector-by-sector OBEX flow is this shape).
  https://www.silabs.com/documents/public/application-notes/AN763.pdf
- **AN533 / AN762 "Modular Bootloader Framework"** — reusable multi-channel framework + source.
  https://www.silabs.com/documents/public/application-notes/AN533.pdf
- C8051F34x datasheet (flash layout, **Security Lock Byte @ 0xFBFF** on 64 KB parts):
  https://www.silabs.com/documents/public/data-sheets/C8051F34x.pdf

**Can the public bootloader code alone reveal Oscill's unpack algorithm? NO.** Stock SiLabs
reference bootloaders flash **plaintext** images (at most a CRC packet) — they neither encrypt nor
compress, so there is no decrypt/decompress algorithm to copy from them. The `.ofw` cipher (§6a,
period-514 additive, shared key) + probable compression are **Oscill's own additions on top of the
reference framework**, present only in the device's bootloader flash. The public code gives the
*skeleton* — flash map (BL 0x0000–0x0400 + last page, app @0x0400), the `FLKEY/PSCTL` self-program
sequence, the DFU packet shape, and the likely meaning of the 2 B/sector (AN763 uses a **CRC-16** —
testable once plaintext exists). The exact unpack is only obtainable by **dumping + disassembling
the device bootloader**; the reference code then lets us quickly isolate the added crypto/decompress
from the standard parts. It accelerates reading a dump — it does not substitute for one.

Open-source / DIY (directly unblock Path A and the read-lock caveat):
- **shraken/gboot** — USB-HID bootloader for C8051F3xx (incl. F34x); ready reference for Path C.
  https://github.com/shraken/gboot   (also gglabs.us/node/3 for F320)
- **x893/C2.Flash** — C2 flash protocol on Arduino/STM32/EFM32 → **build a C2 programmer cheaply**
  instead of buying EC2/ToolStick. https://github.com/x893/C2.Flash
- **ec2drv** (Linux EC2/EC3 driver) https://ec2drv.sourceforge.net/ ; **ec2-new** (see §5).
- **debug-silicon/C8051F34x_Glitch** — voltage-glitch **code-protection bypass** for C8051F340
  (published 2021, MIT). https://github.com/debug-silicon/C8051F34x_Glitch
  - **Attack:** VDD fault injection during the C2 **Block Read** PI command (glitch ~11 µs after the
    bus-switch strobe on the "Write Data Length Code" step) bypasses the lock check without a
    flash-error reset. Reads up to **256 B per successful glitch**; a full 64 KB in <2 min at
    >100 attempts/s. **Non-destructive** — Flash + lock byte (0xFBFF) preserved.
  - **HW:** ChipWhisperer-Lite + BluePill STM32F103 (DIY C2 debugger, C2CK=PB3/C2D=PB4) + target
    board mods (remove regulator, add 50 Ω VDD shunt + SMA) + external 3.3 V. Repo ships the BluePill
    sketch, a ChipWhisperer notebook (`Exp6_glitch_Block_Read.ipynb`), and a PulseView C2 decoder.
    Reads via `FPCTL`/`FPDAT` PI Block Read (code 0x06).
  - **Why it closes BOTH gaps for us:** a dump covers the **bootloader** (0x0000–0x0400 + last page)
    ⇒ disassemble to get the exact decrypt/decompress = the "on-device unpack" §7a Part 3 said was
    not determinable; and the **application** ⇒ plaintext 1.26 = the Path B crib + the D-01 code.
    Non-destructive ⇒ stock bootloader intact ⇒ patched image still flashable via the safe `.ofw`
    path.
  - **Caveats / ordering:** (1) check the lock first — if flash is **not** locked, a plain C2 read
    (ec2-new / DIY C2) dumps everything with **no** glitching; (2) heavy: ChipWhisperer (~$250–350) +
    irreversible board surgery + fault-injection skill; (3) tuned for F340 — glitch params must be
    re-tuned per chip/board; our exact F34x sub-part is still unconfirmed.

## 9. Cipher fully characterized (2026-07-14, independent re-analysis) — CORRECTS §4 Path B / §7a Part 3

A fresh statistical re-analysis of `Uosc125.ofw` + `Uosc126.ofw` **determined the encryption method
exactly** and **overturns the "compressed before encryption" hypothesis**. Confidence: high.
Artifacts: scratchpad `a1_structure.py … a8_hunt.py`; reusable tool `firmware/ofw_crypto.py`
(info / sectors / recover / decrypt / repack, round-trip self-tested).

### 9.1 Method — additive reused keystream (many-time pad), period 514
```
C[s][i] = (P[s][i] + KS[i]) mod 256          # s = sector 0..59, i = byte 0..513
P[s][i] = (C[s][i] - KS[i]) mod 256
```
A byte-wise **additive** stream cipher with a **fixed 514-byte keystream `KS`, reused for every
sector and identical across firmware versions**. Evidence:
- **Additive, not XOR.** On the offset-1 sequence field, `KS[1]=0x06` is constant across 22/24 fitted
  sectors under **addition** but only 12/24 under XOR; the wrap carry `0x0b→0x0c` (which XOR cannot
  produce) is the additive signature.
- **Reused keystream, no chaining.** `(C[6]−C[8]) mod 256` is **zero at every byte except offset 1** —
  the two sectors are the same 512-byte body at different sequence numbers. A one-byte plaintext
  change stays a one-byte ciphertext change ⇒ **no** CBC/stream chaining and **no** S-box diffusion;
  a pure position-wise transform.
- **Period exactly 514.** Ciphertext index-of-coincidence = **8.5 %** at lags 514/1028/1542
  (vs 0.39 % random), flat elsewhere. Each 514-byte sector = one 512-byte C8051F34x flash page + a
  2-byte per-sector field; offset 1 is a linear per-sector sequence field (≈ `0x20·s mod 255`).

### 9.2 NOT compressed — overturns §4 Path B / §7a Part 3
`C125 − C126 = P125 − P126` (the shared keystream cancels) is **8.9 % zero and structured**: sectors
6/22/24 are byte-identical across versions and sectors 30–59 changed almost entirely. Whole-image
compression would misalign everything after the first changed byte → ~0 % cross-version coincidence;
8.9 % structured coincidence is the opposite. The earlier "≈0.4 % page-XOR ⇒ likely compressed"
reading was an **artifact of averaging in the duplicated data pages** (they inflate/deflate the mean);
on genuinely distinct sectors the plaintext is simply **high-entropy firmware data, not compressed**.
⇒ There is **no decompression stage to reverse** — recovery is a plain additive subtraction (this
removes the §7a-Part-3 worry that a decompressor would also need reversing).

### 9.3 Why the file alone still does not decrypt (confirms §4's practical verdict, corrects the reason)
`KS` is a **stored 514-byte table** (period 514 rules out any mod-256 LCG/LFSR, whose period ≤256),
resident **only in the device bootloader**. It is **not** in the PC software — three independent
checks: (a) the `.ofw` loader passes the payload verbatim (Part 1 / §3); (b) `FWupdateKey` is a GUI
button control (`FWupdateKey_Click`), **not** a key — the §3-old "app holds a key" note was a misread;
(c) a byte-level scan of `oscill.exe`, `oscilink.dll`, `SiUSBXp.dll`, `wcl.dll`, `SiInfo.dll`,
`TestBT.exe` for an embedded 514-byte additive keystream found **nothing**. Ciphertext-only recovery
is insufficient: only **37/514** columns are background-dominated (mode-recovery drops entropy
7.98→7.07 but yields no readable code/strings), the sector bodies are high-entropy, and the firmware's
guaranteed ASCII cribs (`Uosc`, `VSW`, `VNM`, `M1`, `O1`, `RT`, …) are ≤4 bytes — too short to lever a
reused-keystream break amid high-entropy neighbours.

### 9.4 Full-unpack recipe (target unchanged from §4 Path A, mechanics now exact & simpler)
1. Dump **one** flash page (any) over **C2** (§5/§8) → one known-plaintext sector.
2. `python3 firmware/ofw_crypto.py recover <ofw> <plain_sector.bin> ks.bin` → `KS = (C−P) mod 256`.
   **One** known page fixes all 514 keystream bytes (shared by every sector and both versions).
3. `ofw_crypto.py decrypt <ofw> ks.bin image.bin` → plaintext flash image (no decompression).
4. Patch (e.g. D-01), then `ofw_crypto.py repack image.bin ks.bin <template.ofw> new.ofw` → a valid
   `.ofw` the stock bootloader accepts, subject to the 2-byte per-sector field (likely a checksum —
   confirm its algorithm against the dump before trusting a re-pack).

**Net:** the "encryption method" question is **answered** (additive period-514 reused keystream, not
compression); the "unpack" is **blocked only by needing one known page**, and the mechanical tooling
to finish it the moment that page exists is in place (`ofw_crypto.py`).

### 9.5 Can 8051 opcode statistics break it without hardware? — TESTED 2026-07-14, NO (depth-limited)
Reused keystream + a known language (8051 machine code) is in principle a "many-time-pad broken by a
language model". Tested (scratchpad `a9_codemodel.py`): maximum-likelihood per-column recovery against
an 8051 byte-frequency model, using the code pages (30–59, which recompile ~entirely between versions;
duplicated data pages sit in 0–29). **It fails:** per-column mode-fraction on code pages is
**0.055 ≈ the 60-sample chance floor**; ML-decryption stays at entropy **7.86** with only random ASCII
and **no** register-name cribs (`ALL120` samples: same). Reason: the keystream period equals the page
size, so each key byte is masked by only ~60 code-bytes (120 incl. data, but data doesn't fit the
model), and 8051's modest marginal skew (0x00 ≈ 10 %) cannot overcome the 256-way per-column ambiguity
at that depth — this is exactly why the earlier EM attempt gave only `0x92/0x28` non-convergence.
**Lever:** depth scales with firmware versions — each adds ~30 code samples per key byte; older
versions share the same bootloader keystream, and recompilation reshuffles addresses → independent
samples from the same 8051 distribution.

**Tested with 3 versions (2026-07-14): still does not break.** Acquired `Uosc123.ofw` (§9.6) and
confirmed it shares the keystream, giving 180 sectors under one KS. ML/marginal recovery over all 180
drops entropy 7.98 → **7.26** but produces **0 crib hits** and only garbage strings — the same
mode-flattening the earlier EM run saw, not a decryption. Reason: the keystream period = the page
size caps depth at (sectors × versions), the 8051 marginal is too flat (0x00 ≈ 10 %), and much of the
image is high-entropy data. Estimated need ≈ 8–16 versions for a marginal+bigram attack; only **three
are published** (1.24/1.22 exist in the changelog but are unobtainable — see §9.6). **File-only route
is exhausted; the one-known-page (C2) break remains the reliable route.**

### 9.6 Firmware inventory & numbering (2026-07-14 download effort)
Vendor numbering (from the install-CD doc `368-usbuartfwnumbering.html`): images are **uosc X.YZ** —
`X` = family/generation, `Y` = hardware-schematic revision, `Z` = firmware version. The bootloader
permanently stores the device name (`uosc`) + platform `X.Y`; a `.ofw` loads only if its `X.Y` matches
(⇒ **all 1.2Z images are decrypted by the same 1.2 bootloader = same keystream**, confirmed below).
Vendor changelog (`349-usbuartfwhist.html`) lists **v1.22, v1.23, v1.24, v1.25, v1.26**.

| Version | File | Status | Keystream |
|---|---|---|---|
| 1.23 | `http://oscill.com/files/fw_u123.zip` (= `fw_u12.zip`, also in `isoscill.zip`) | **downloaded** | **shared** (1.23 sector0 ≡ 1.25 sector16, byte-identical) |
| 1.24 | — | changelog only; `fw_u124.zip` 404, no Wayback archive | (unobtained) |
| 1.25 | `http://oscill.com/files/fw_u125.zip` | in repo | shared |
| 1.26 | `http://oscill.com/files/fw_u126.zip` | in repo | shared |
| 1.22 | — | changelog only; `fw_u122.zip` 404 | (unobtained) |

Also fetched `http://oscill.com/files/isoscill.zip` → `oscill.iso` (45 MB install CD): firmware docs
(bootloader / numbering / history / chip-programmer FAQ), an older `oscill.exe` build, and
`files/fw_u12.zip` (= the same 1.23). No additional firmware version. The vendor only publishes the
latest few; 1.22/1.24 are not downloadable (404 everywhere, no web.archive.org copies of the binaries).
Downloaded `Uosc123.ofw` kept in `firmware/`.
