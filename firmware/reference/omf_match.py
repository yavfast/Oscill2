#!/usr/bin/env python3
"""Extract byte-exact Keil C51 runtime routines from C51*.LIB (OMF51) and locate
them in the encrypted vendor image via lattice-K validation -> recover contiguous K."""
import sys,collections; sys.path.insert(0,'/hdd/PROJECTS/Oscill2/firmware')
from mask_lib import load, known_K, FILES

LEN=[1,2,3,1,1,2,1,1,1,1,1,1,1,1,1,1, 3,2,3,1,1,2,1,1,1,1,1,1,1,1,1,1,
3,2,1,1,2,2,1,1,1,1,1,1,1,1,1,1, 3,2,1,1,2,2,1,1,1,1,1,1,1,1,1,1,
2,2,2,3,2,2,1,1,1,1,1,1,1,1,1,1, 2,2,2,3,2,2,1,1,1,1,1,1,1,1,1,1,
2,2,2,3,2,2,1,1,1,1,1,1,1,1,1,1, 2,2,2,1,2,3,2,2,2,2,2,2,2,2,2,2,
2,2,2,1,1,3,2,2,2,2,2,2,2,2,2,2, 3,2,2,1,2,2,1,1,1,1,1,1,1,1,1,1,
2,2,2,1,1,1,2,2,2,2,2,2,2,2,2,2, 2,2,2,1,3,3,3,3,3,3,3,3,3,3,3,3,
2,2,2,1,1,2,1,1,1,1,1,1,1,1,1,1, 2,2,2,1,1,3,1,1,2,2,2,2,2,2,2,2,
1,2,1,1,1,2,1,1,1,1,1,1,1,1,1,1, 1,2,1,1,1,2,1,1,1,1,1,1,1,1,1,1]
def make_template(code):
    t=[]; i=0
    while i<len(code):
        op=code[i]; ln=LEN[op]; t.append((op,True))
        for k in range(1,ln):
            if i+k<len(code): t.append((code[i+k],False))
        i+=ln
    return t

def parse_lib(path):
    data=open(path,'rb').read(); i=0; cur=None; segs=collections.defaultdict(dict); mods={}
    while i+3<=len(data):
        rt=data[i]; ln=data[i+1]|(data[i+2]<<8)
        if ln==0: break
        body=data[i+3:i+3+ln-1]
        if rt==0x02:
            nlen=body[0]; cur=body[1:1+nlen].decode('latin1'); segs=collections.defaultdict(dict)
        elif rt in (0x06,0x07) and len(body)>=3:      # Content record (OMF51 uses 0x07)
            segid=body[0]; off=body[1]|(body[2]<<8)
            for k,b in enumerate(body[3:]): segs[segid][off+k]=b
        elif rt==0x04:                                 # Module End
            if cur and segs:
                best=max(segs.values(),key=len); lo,hi=min(best),max(best)
                mods[cur]=bytes(best.get(x,0) for x in range(lo,hi+1))
            cur=None; segs=collections.defaultdict(dict)
        i+=3+ln
    return mods

def scan(sec,K,tmpl,min_ov=3):
    hits=[]
    for f in FILES:
        for si in range(60):
            page=sec[f][si]
            for o in range(0,514-len(tmpl)):
                ov=mt=0; bad=False
                for j,(tb,fx) in enumerate(tmpl):
                    if not fx: continue
                    col=o+j
                    if 2<=col<514 and col in K:
                        ov+=1
                        if (page[col]-K[col])&0xFF==tb: mt+=1
                        else: bad=True; break
                if bad or ov<min_ov or mt!=ov: continue
                hits.append((f[4:7],si,o,ov))
    return hits

D="/tmp/claude-1000/-hdd-PROJECTS-Oscill2/7c2bf032-0040-4c83-9347-981e61b2e570/scratchpad/keil/LIB"
sec,_=load(); K=known_K()
K.update({5:0x9f,29:0xc8,37:0xdc,53:0xe1,61:0x05,69:0xc1,77:0x11,85:0x30,93:0x22,101:0x0d,109:0x8d,117:0xc1})

for lib in ("C51S.LIB","C51L.LIB","C51FPS.LIB"):
    mods=parse_lib(f"{D}/{lib}")
    routines={k:v for k,v in mods.items() if k.startswith('?C?') and len(v)>=12}
    print(f"\n=== {lib}: {len(routines)} code routines (>=12B) ===")
    total_hits=0
    for name,code in sorted(routines.items(), key=lambda kv:-len(kv[1]))[:14]:
        tmpl=make_template(code); nfix=sum(1 for _,fx in tmpl if fx)
        hits=scan(sec,K,tmpl,min_ov=3)
        if hits:
            total_hits+=len(hits)
            print(f"  {name:12s} {len(code):3d}B ({nfix} fix) -> HIT {hits[:3]}")
    if not total_hits: print("  (no >=3-overlap hits)")
