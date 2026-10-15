#!/usr/bin/env python3
"""Arma web/ del Kenti Terrestre a partir de las interfaces de cada módulo."""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "parches"))
from aves_estado import apply as patch_aves_estado
from insectos_extra import apply as patch_insectos
SRC = Path(sys.argv[1]); OUT = Path(__file__).parent / "launcher" / "web"
MODS = {  # id: (archivo, nombre)
 "flora": ("Botanico.html", "Flora"), "aves": ("Ornitologico.html", "Aves"),
 "mamiferos": ("Mastozoologico.html", "Mamíferos"), "herpetos": ("Herpetologico.html", "Herpetofauna"),
 "insectos": ("Entomologico.html", "Entomología"), "global": ("master.html", "Análisis global"),
}
FACES = """<style>
@font-face{font-family:"Public Sans";src:url(/fuentes/PublicSans-Regular.woff2) format("woff2");font-weight:400;font-display:swap}
@font-face{font-family:"Public Sans";src:url(/fuentes/PublicSans-Medium.woff2) format("woff2");font-weight:500;font-display:swap}
@font-face{font-family:"Public Sans";src:url(/fuentes/PublicSans-SemiBold.woff2) format("woff2");font-weight:600;font-display:swap}
@font-face{font-family:"Public Sans";src:url(/fuentes/PublicSans-Bold.woff2) format("woff2");font-weight:700;font-display:swap}
@font-face{font-family:"Source Serif 4";src:url(/fuentes/SourceSerif4-Roman.ttf) format("truetype");font-weight:200 900;font-style:normal;font-display:swap}
@font-face{font-family:"Source Serif 4";src:url(/fuentes/SourceSerif4-Italic.ttf) format("truetype");font-weight:200 900;font-style:italic;font-display:swap}
@font-face{font-family:"IBM Plex Mono";src:url(/fuentes/IBMPlexMono-Regular.woff2) format("woff2");font-weight:400;font-display:swap}
@font-face{font-family:"IBM Plex Mono";src:url(/fuentes/IBMPlexMono-Medium.woff2) format("woff2");font-weight:500;font-display:swap}
</style>
"""
BAR = """<div id="kt-bar" style="display:flex;align-items:center;gap:12px;padding:6px 16px;background:var(--surface-2,#eaeee5);border-bottom:1px solid var(--line,#dde2d6);font:500 13px/1.2 var(--sans,system-ui,sans-serif);color:var(--ink-2,#465040)"><a href="/" onclick="event.preventDefault();setTimeout(function(){location.href='/'},700)" style="color:var(--accent,#3d6b1c);text-decoration:none;font-weight:600">&larr; Kenti Terrestre</a><span style="opacity:.6">/</span><span>%s</span></div>
"""
ESTADO = {"aves": "aves-estado-ar.json", "mamiferos": "mamiferos-estado-ar.json", "herpetos": "herpetos-estado-ar.json"}
def patch_master(s):
    """Dos correcciones al consolidador, halladas con las simulaciones (verificacion/sims.py):
    1) el encabezado de la matriz se elige primero por cantidad de celdas de texto (antes la suma con las
       celdas numéricas podía preferir una fila de datos cuando la planilla tenía muchas celdas vacías);
    2) los códigos de sitio se comparan sin ceros a la izquierda en el sufijo numérico (TE-1 = TE-01)."""
    a = "const score = txt + numeric;"; assert a in s; s = s.replace(a, "const score = txt * 1000 + Math.min(numeric, 999);")
    a = 'const norm = s => String(s ?? "").normalize("NFD")'; assert a in s
    i = s.index(a); j = s.index("\n", i)
    s = s[:j+1] + 'const normSite = s => norm(s).replace(/([a-z])0+(?=\\d)/g, "$1");\n' + s[j+1:]
    a = ".map(norm).filter(Boolean); return [...new Set(ks)]; }"; assert a in s; s = s.replace(a, ".map(normSite).filter(Boolean); return [...new Set(ks)]; }")
    a = "const k = norm(label); if (!k) return null;"; assert a in s; s = s.replace(a, "const k = normSite(label); if (!k) return null;")
    a = "const k = norm(en.matrix.sites[j]);"; assert a in s; s = s.replace(a, "const k = normSite(en.matrix.sites[j]);")
    return s

for gid, (f, nombre) in MODS.items():
    s = (SRC / f).read_text(encoding="utf-8")
    n_api = len(re.findall(r'"/api/', s))
    if gid == "global": s = patch_master(s)
    if gid == "insectos": s = patch_insectos(s)                 # estimadores de riqueza y hoja de referencia ecológica
    if gid in ESTADO: s = patch_aves_estado(s, ESTADO[gid])   # hoja de estado de conservación en el Excel de descarga
    s = s.replace('"/api/', '"api/')                       # relativo a /g/<id>/
    assert '/api/' not in s.replace('"api/', ''), gid
    s = s.replace("url(fuentes/", "url(/fuentes/").replace('href="icono.png"', 'href="/icono.png"')
    # fuentes que la página incrusta al exportar figuras: ruta absoluta (la relativa daba 404 bajo /g/<id>/)
    s = s.replace("fetch(`fuentes/", "fetch(`/fuentes/")
    if "@font-face" not in s:
        s = s.replace("</head>", FACES + "</head>", 1)
    s, k = re.subn(r"<body[^>]*>", lambda m: m.group(0) + "\n" + BAR % nombre, s, count=1)
    assert k == 1, gid
    (OUT / "g" / f"{gid}.html").write_text(s, encoding="utf-8")
    print(gid, len(s), "api:", n_api)

b=(SRC/"Botanico.html").read_text(encoding="utf-8")
logo=re.search(r"data:image/webp;base64,[A-Za-z0-9+/=]+",b).group(0)
(OUT/"index.html").write_text((Path(__file__).parent/"home.html").read_text(encoding="utf-8").replace("__LOGO__",logo),encoding="utf-8")
print("home ok")
