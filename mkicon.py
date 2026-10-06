import io, struct
from pathlib import Path
from PIL import Image
HERE = Path(__file__).parent / "launcher"
def dib(im):
    w, h = im.size
    hdr = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    px = im.tobytes("raw", "BGRA")
    rows = [px[y * w * 4:(y + 1) * w * 4] for y in range(h)][::-1]
    mask = b"\x00" * (((w + 31) // 32) * 4 * h)
    return hdr + b"".join(rows) + mask
base = Image.open(HERE / "web" / "icono.png").convert("RGBA")
icons = []
for s in (16, 24, 32, 48, 64, 128, 256):
    im = base.resize((s, s), Image.LANCZOS)
    if s >= 64:
        b = io.BytesIO(); im.save(b, "PNG"); data = b.getvalue()
    else:
        data = dib(im)
    icons.append((s, data))
group = struct.pack("<HHH", 0, 1, len(icons)) + b"".join(
    struct.pack("<BBBBHHIH", s % 256, s % 256, 0, 0, 1, 32, len(d), i + 1) for i, (s, d) in enumerate(icons))
MANIFEST = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <assemblyIdentity type="win32" name="Kenti.App" version="0.1.0.0"/>
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3"><security><requestedPrivileges>
    <requestedExecutionLevel level="asInvoker" uiAccess="false"/>
  </requestedPrivileges></security></trustInfo>
  <application xmlns="urn:schemas-microsoft-com:asm.v3"><windowsSettings>
    <dpiAware xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings">true</dpiAware>
  </windowsSettings></application>
</assembly>
"""
leaves = [(3, i + 1, d) for i, (_, d) in enumerate(icons)] + [(14, 1, group), (24, 1, MANIFEST)]
def build_rsrc(leaves):
    types = sorted({t for t, _, _ in leaves})
    off = 16 + 8 * len(types)
    type_off = {}
    for t in types:
        type_off[t] = off
        off += 16 + 8 * sum(1 for tt, _, _ in leaves if tt == t)
    lang_off = []
    for _ in leaves:
        lang_off.append(off); off += 16 + 8
    de_off = []
    for _ in leaves:
        de_off.append(off); off += 16
    data_off = []
    for _, _, d in leaves:
        off = (off + 7) & ~7; data_off.append(off); off += len(d)
    buf = bytearray((off + 7) & ~7)
    def hdr(o, n): struct.pack_into("<IIHHHH", buf, o, 0, 0, 0, 0, 0, n)
    hdr(0, len(types))
    for k, t in enumerate(types):
        struct.pack_into("<II", buf, 16 + 8 * k, t, 0x80000000 | type_off[t])
    for t in types:
        idx = sorted((i for i, (tt, _, _) in enumerate(leaves) if tt == t), key=lambda i: leaves[i][1])
        hdr(type_off[t], len(idx))
        for k, i in enumerate(idx):
            struct.pack_into("<II", buf, type_off[t] + 16 + 8 * k, leaves[i][1], 0x80000000 | lang_off[i])
    relocs = []
    for i, (t, rid, d) in enumerate(leaves):
        hdr(lang_off[i], 1)
        struct.pack_into("<II", buf, lang_off[i] + 16, 0x0409, de_off[i])
        struct.pack_into("<IIII", buf, de_off[i], data_off[i], len(d), 0, 0)
        relocs.append(de_off[i])
        buf[data_off[i]:data_off[i] + len(d)] = d
    return bytes(buf), relocs
rsrc, relocs = build_rsrc(leaves)
raw_ptr = 20 + 40
reloc_ptr = raw_ptr + len(rsrc)
sym_ptr = reloc_ptr + 10 * len(relocs)
coff = bytearray()
coff += struct.pack("<HHIIIHH", 0x8664, 1, 0, sym_ptr, 1, 0, 0x0004)
coff += struct.pack("<8sIIIIIIHHI", b".rsrc", 0, 0, len(rsrc), raw_ptr, reloc_ptr, 0, len(relocs), 0, 0x40000040)
coff += rsrc
for r in relocs:
    coff += struct.pack("<IIH", r, 0, 0x0003)
coff += struct.pack("<8sIhHBB", b".rsrc", 0, 1, 0, 3, 0)
coff += struct.pack("<I", 4)
(HERE / "rsrc_windows_amd64.syso").write_bytes(bytes(coff))
print("syso", len(coff))
