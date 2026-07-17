"""Shared library for the .ofw mask 'sudoku' — import from subagent scripts.
Cipher: C[s][i] = (P[s][i] + K[i]) mod 256, period 514, K shared across 3 versions.
Sector = 514 bytes: col0=CRC(content checksum), col1=SEQ, col2..513 = 512-byte flash page.
Logical page L (flash addr 0x0400 + L*0x200) decoded from SEQ: K[1]=0x06, L=(8*(C[1]-6))%255."""
import collections
SECTOR = 514
FW = b"FW:"
BASE = "/hdd/PROJECTS/Oscill2/firmware/"
FILES = ["Uosc123.ofw", "Uosc125.ofw", "Uosc126.ofw"]

def _payload(p):
    b = open(BASE + p, "rb").read()
    return b[b.find(FW) + 3:]

def load():
    """-> dict{version: [60 sectors]}, and flat list allsec."""
    sec = {f: [_payload(f)[i*SECTOR:(i+1)*SECTOR] for i in range(60)] for f in FILES}
    allsec = [sec[f][i] for f in FILES for i in range(60)]
    return sec, allsec

def known_K():
    """Return dict col->K for the 66 PROVEN/CONFIRMED bytes."""
    sec, allsec = load()
    K = {}
    # 64 lattice bytes: body offset==4 mod8 -> plaintext 0xFF -> K=(mode+1)&0xFF
    for c in range(2, SECTOR):
        if (c - 2) % 8 == 4:
            cnt = collections.Counter(a[c] for a in allsec)
            (mb, mn), (_, m2) = cnt.most_common(2)
            if (mn - m2) / len(allsec) >= 0.10:
                K[c] = (mb + 1) & 0xFF
    K[1] = 0x06            # SEQ keystream byte
    K[2] = 0x33            # reset LJMP: P[L0][0]=0x02
    return K

def logical_L(sector_bytes):
    L = (8 * ((sector_bytes[1] - 0x06) & 0xFF)) % 255
    return 'E' if L == 254 else L

def L_map():
    """version -> {L: file_index}."""
    sec, _ = load()
    return {f: {logical_L(sec[f][i]): i for i in range(60)} for f in FILES}

# 8051 opcode validity helper: bytes that are valid opcodes (all 256 are technically
# defined on 8051 except 0xA5 which is reserved/illegal). Use for weak grammar checks.
ILLEGAL_8051 = {0xA5}

if __name__ == "__main__":
    K = known_K(); Lm = L_map()
    print(f"known K bytes: {len(K)}  (cols: 1,2 + 64 lattice)")
    print(f"K[1]={K[1]:#x} K[2]={K[2]:#x}")
    for f in FILES:
        print(f"  {f[4:7]}: L=0 at file-sector {Lm[f][0]}, L=1 at {Lm[f].get(1)}")
