import sys, re
sys.path.insert(0,'.')
from elf import Elf
E = Elf('work/lib/arm64-v8a/libcocos2dcpp.so')
d = E.d

def find(pat, limit=60):
    out=[]
    for m in re.finditer(re.escape(pat.encode()), d):
        o=m.start()
        if o>0 and d[o-1]!=0: continue
        va=E.off2va(o)
        if va: out.append((va, E.cstr(va)))
        if len(out)>=limit: break
    return out
