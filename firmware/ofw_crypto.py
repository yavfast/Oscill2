#!/usr/bin/env python3
"""
ofw_crypto.py — Oscill `.ofw` firmware container tool.

Determined by cryptanalysis of Uosc125.ofw / Uosc126.ofw (see
docs/firmware_update_method.spike.md §9):

CONTAINER
  offset 0    : magic  75 EF 00
  then        : "\\r\\n" "Oscill.com oscilloscope firmware.\\r\\n"
                "Target: <name>\\r\\n" "Version: <x.yz>\\r\\n" "Date: <DDMMYYYY>\\r\\n"
                "FW:"  <payload>
  payload     : starts right after "FW:" (offset 0x58 for the stock files),
                length = 60 sectors * 514 bytes = 30840 bytes

PAYLOAD ENCRYPTION  (device bootloader decrypts internally)
  Additive stream cipher with a FIXED 514-byte keystream KS, reused for
  every sector and identical across firmware versions:

        C[s][i] = (P[s][i] + KS[i]) & 0xFF        # s = sector, i = 0..513
        P[s][i] = (C[s][i] - KS[i]) & 0xFF

  - period exactly 514 (each 514-byte sector = one 512-byte C8051F34x flash
    page + a 2-byte per-sector field; offset 1 carries a linear sequence
    field, KS[1] = 0x06).
  - NO chaining, NO compression, NO XOR — a single-byte plaintext change
    stays a single-byte ciphertext change (proven: sectors 6 vs 8 differ
    only at offset 1).

The keystream KS is NOT present in the PC software; it lives in the device
bootloader. Recover it from ONE known-plaintext page (e.g. a C2 flash dump),
then this tool decrypts/repacks any image.

Usage:
  ofw_crypto.py info      <file.ofw>
  ofw_crypto.py sectors   <file.ofw>                 # per-sector header/entropy
  ofw_crypto.py recover   <file.ofw> <plain.bin> <ks.bin>   # KS = C - P
  ofw_crypto.py decrypt   <file.ofw> <ks.bin> <out.bin>
  ofw_crypto.py repack    <plain.bin> <ks.bin> <template.ofw> <out.ofw>
"""
import sys, math, collections

SECTOR = 514
FW_TAG = b"FW:"


def parse(blob: bytes) -> dict:
    """Split an .ofw into its plaintext header fields and the raw payload."""
    idx = blob.find(FW_TAG)
    if idx < 0:
        raise ValueError("no 'FW:' tag — not an .ofw container")
    head = blob[:idx]
    payload = blob[idx + len(FW_TAG):]

    def field(name):
        m = head.find(name)
        if m < 0:
            return None
        start = m + len(name)
        end = head.find(b"\r\n", start)
        return head[start:end if end >= 0 else None].decode("latin1")

    return {
        "magic": blob[:3].hex(),
        "target": field(b"Target: "),
        "version": field(b"Version: "),
        "date": field(b"Date: "),
        "payload_off": idx + len(FW_TAG),
        "payload": payload,
        "n_sectors": len(payload) // SECTOR,
        "remainder": len(payload) % SECTOR,
    }


def entropy(b: bytes) -> float:
    if not b:
        return 0.0
    c = collections.Counter(b)
    n = len(b)
    return -sum(v / n * math.log2(v / n) for v in c.values())


def decrypt(payload: bytes, ks: bytes) -> bytes:
    """P = (C - KS) mod 256, keystream reused every SECTOR bytes."""
    if len(ks) != SECTOR:
        raise ValueError(f"keystream must be {SECTOR} bytes, got {len(ks)}")
    out = bytearray(len(payload))
    for i, c in enumerate(payload):
        out[i] = (c - ks[i % SECTOR]) & 0xFF
    return bytes(out)


def encrypt(image: bytes, ks: bytes) -> bytes:
    """C = (P + KS) mod 256."""
    if len(ks) != SECTOR:
        raise ValueError(f"keystream must be {SECTOR} bytes, got {len(ks)}")
    out = bytearray(len(image))
    for i, p in enumerate(image):
        out[i] = (p + ks[i % SECTOR]) & 0xFF
    return bytes(out)


def recover_keystream(payload: bytes, plain: bytes) -> bytes:
    """KS[i] = (C - P) mod 256, averaged/validated across all sectors.

    `plain` may be one 514-byte sector or the whole plaintext image; every
    514-aligned position must agree on KS or the known plaintext is wrong.
    """
    ks: list[int | None] = [None] * SECTOR
    conflicts = 0
    n = min(len(payload), len(plain))
    for i in range(n):
        pos = i % SECTOR
        k = (payload[i] - plain[i]) & 0xFF
        if ks[pos] is None:
            ks[pos] = k
        elif ks[pos] != k:
            conflicts += 1
    missing = [i for i, v in enumerate(ks) if v is None]
    if conflicts:
        print(f"WARNING: {conflicts} keystream conflicts — known plaintext likely wrong/misaligned",
              file=sys.stderr)
    if missing:
        print(f"WARNING: {len(missing)} keystream bytes unresolved (need more plaintext)",
              file=sys.stderr)
    return bytes(k if k is not None else 0 for k in ks)


def _sectors(payload):
    n = len(payload) // SECTOR
    return [payload[s * SECTOR:(s + 1) * SECTOR] for s in range(n)]


def cmd_info(path):
    p = parse(open(path, "rb").read())
    print(f"file        : {path}")
    print(f"magic       : {p['magic']}")
    print(f"target      : {p['target']}")
    print(f"version     : {p['version']}")
    print(f"date        : {p['date']}")
    print(f"payload off : 0x{p['payload_off']:x}")
    print(f"payload len : {len(p['payload'])}  = {p['n_sectors']} sectors x {SECTOR}  (rem {p['remainder']})")
    print(f"entropy     : {entropy(p['payload']):.3f} bits/byte (encrypted)")


def cmd_sectors(path):
    p = parse(open(path, "rb").read())
    secs = _sectors(p["payload"])
    print(f"{len(secs)} sectors; per-sector offset-1 seq byte + entropy:")
    for i, s in enumerate(secs):
        print(f"  sector {i:2d}: b0={s[0]:02x} seq1={s[1]:02x} entropy={entropy(s):.2f}")


def cmd_recover(path, plainpath, ksout):
    p = parse(open(path, "rb").read())
    plain = open(plainpath, "rb").read()
    ks = recover_keystream(p["payload"], plain)
    open(ksout, "wb").write(ks)
    print(f"wrote keystream ({len(ks)} bytes) -> {ksout}")


def cmd_decrypt(path, kspath, outpath):
    p = parse(open(path, "rb").read())
    ks = open(kspath, "rb").read()
    img = decrypt(p["payload"], ks)
    open(outpath, "wb").write(img)
    print(f"decrypted {len(img)} bytes -> {outpath}  (entropy {entropy(img):.3f})")


def cmd_repack(plainpath, kspath, template, outpath):
    tmpl = open(template, "rb").read()
    idx = tmpl.find(FW_TAG) + len(FW_TAG)
    header = tmpl[:idx]
    img = open(plainpath, "rb").read()
    ks = open(kspath, "rb").read()
    payload = encrypt(img, ks)
    open(outpath, "wb").write(header + payload)
    print(f"repacked {len(payload)} bytes payload -> {outpath}")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd, rest = argv[1], argv[2:]
    try:
        {
            "info": cmd_info,
            "sectors": cmd_sectors,
            "recover": cmd_recover,
            "decrypt": cmd_decrypt,
            "repack": cmd_repack,
        }[cmd](*rest)
    except KeyError:
        print(f"unknown command: {cmd}\n{__doc__}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
