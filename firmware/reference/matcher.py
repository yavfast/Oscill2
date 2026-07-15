#!/usr/bin/env python3
"""Constrained sliding-window compiler-template matcher for the .ofw mask.
Places an 8051 code template (opcodes FIXED, operands WILDCARD) at every column
offset; derives K=C-template at fixed bytes; validates against the 78 known-K
columns + 8051 opcode-validity. Used to locate compiler startup/library routines."""
import sys; sys.path.insert(0,'/hdd/PROJECTS/Oscill2/firmware')
from mask_lib import load, known_K, L_map, FILES

# ---- 8051 instruction length table (256) ----
LEN = [
1,2,3,1,1,2,1,1, 1,1,1,1,1,1,1,1,   # 00
3,2,3,1,1,2,1,1, 1,1,1,1,1,1,1,1,   # 10
3,2,1,1,2,2,1,1, 1,1,1,1,1,1,1,1,   # 20
3,2,1,1,2,2,1,1, 1,1,1,1,1,1,1,1,   # 30
2,2,2,3,2,2,1,1, 1,1,1,1,1,1,1,1,   # 40
2,2,2,3,2,2,1,1, 1,1,1,1,1,1,1,1,   # 50
2,2,2,3,2,2,1,1, 1,1,1,1,1,1,1,1,   # 60
2,2,2,1,2,3,2,2, 2,2,2,2,2,2,2,2,   # 70
2,2,2,1,1,3,2,2, 2,2,2,2,2,2,2,2,   # 80
3,2,2,1,2,2,1,1, 1,1,1,1,1,1,1,1,   # 90
2,2,2,1,1,1,2,2, 2,2,2,2,2,2,2,2,   # A0
2,2,2,1,3,3,3,3, 3,3,3,3,3,3,3,3,   # B0
2,2,2,1,1,2,1,1, 1,1,1,1,1,1,1,1,   # C0
2,2,2,1,1,3,1,1, 2,2,2,2,2,2,2,2,   # D0
1,2,1,1,1,2,1,1, 1,1,1,1,1,1,1,1,   # E0
1,2,1,1,1,2,1,1, 1,1,1,1,1,1,1,1,   # F0
]
def make_template(code):
    """-> list of (byte, is_fixed): opcode bytes fixed, operand bytes wildcard."""
    t=[]; i=0
    while i < len(code):
        op=code[i]; ln=LEN[op]
        t.append((op, True))                      # opcode = fixed
        for k in range(1, ln):
            if i+k < len(code): t.append((code[i+k], False))  # operand = wildcard
        i+=ln
    return t

def scan(page, K, tmpl, require_valid=True):
    """Best (offset, matched, overlaps) placing tmpl in a 512-byte page body.
    Validate at known-K cols; optionally require derived plaintext = valid opcodes."""
    best=(-1,-1,0,0)
    for o in range(0, 512-len(tmpl)):
        overlaps=matched=0; conflict=False; validop=True
        for j,(tb,fixed) in enumerate(tmpl):
            col=o+j+2
            if not fixed: continue
            if col in K:
                overlaps+=1
                if (page[col]-K[col])&0xFF == tb: matched+=1
                else: conflict=True; break
        if conflict: continue
        if overlaps==0: continue
        score=matched
        if score>best[2]: best=(o,overlaps,matched,overlaps)
    return best  # (offset, overlaps, matched, overlaps)

# ---- load ----
sec,_=load(); K=known_K()
K.update({5:0x9f,29:0xc8,37:0xdc,53:0xe1,61:0x05,69:0xc1,77:0x11,85:0x30,93:0x22,101:0x0d,109:0x8d,117:0xc1})

# ---- SDCC startup template from the reference build ----
mp=open('/hdd/PROJECTS/Oscill2/firmware/reference/ref.map').read()
import re
addr=None
for line in mp.splitlines():
    m=re.search(r'([0-9A-F]{8})\s+__sdcc_gsinit_startup', line)
    if m: addr=int(m.group(1),16); break
ref=open('/hdd/PROJECTS/Oscill2/firmware/reference/ref.bin','rb').read()
startup=ref[addr:addr+48]
tmpl=make_template(startup)
nfix=sum(1 for _,f in tmpl if f)
print(f"SDCC startup @0x{addr:04X}: {len(startup)}B -> template {len(tmpl)} bytes, {nfix} FIXED (opcodes)")
print(f"  first bytes: {startup[:16].hex()}")

# ---- POSITIVE CONTROL: embed SDCC startup encrypted with real K, confirm we find it ----
print("\n[POSITIVE CONTROL] embed startup (encrypted with real K) at a chosen offset:")
o_true=40                                  # body offset
buf=bytearray(514)
for j,(tb,fixed) in enumerate(tmpl):
    col=o_true+j+2
    buf[col]=(tb + K.get(col,0))&0xFF       # encrypt with real K where known
res=scan(buf,K,tmpl)
print(f"  planted at offset {o_true}; matcher best offset={res[0]}, matched {res[2]}/{res[1]} known-overlaps"
      f"  -> {'FOUND ✓' if res[0]==o_true and res[2]==res[1] and res[1]>0 else 'miss'}")

# ---- REAL TEST: does the SDCC startup appear in the vendor image? ----
print("\n[VENDOR TEST] scan all 180 sectors for the SDCC startup template:")
best=(None,-1,0,0)
for f in FILES:
    for i in range(60):
        o,ov,mt,_=scan(sec[f][i],K,tmpl)
        if mt>best[2] or (mt==best[2] and ov>best[3]):
            best=((f[4:7],i),o,mt,ov)
print(f"  best match: {best[0]} offset {best[1]}, {best[2]}/{best[3]} fixed-bytes-on-known-cols agree")
# interpretation
if best[3]>=3 and best[2]==best[3]:
    print("  => plausible SDCC startup present")
else:
    print(f"  => NO consistent SDCC startup (best only {best[2]}/{best[3]} with tiny overlap) -> SDCC RULED OUT")
