#!/usr/bin/env python3
"""Aves: hoja «6 Estado de conservación» en el Excel de descarga.

Agrega al libro exportado una hoja con orden, familia y estado de conservación nacional de cada
especie de la tabla, tomados de launcher/web/datos/aves-estado-ar.json (Resolución 795-E/2017,
Anexos I-III). Es sólo para la planilla: no cambia la tabla, los índices ni ningún cálculo, y si el
archivo de datos no se puede leer el libro sale igual, sin la hoja.

Uso: lo importa prep.py (apply(texto) -> texto); también corre solo sobre la página ya generada:
    python3 parches/aves_estado.py launcher/web/g/aves.html
"""
import sys
from pathlib import Path

MARCA = "// 6 · Estado de conservación nacional"
ANCLA = "  return {blob: await workbookBlob(sheets, X, `${GROUP.nombre} · resultados`), name: M.file};"

JS = r'''  // 6 · Estado de conservación nacional (Res. 795-E/2017): sólo en la planilla, no entra en ningún análisis
  try {
    const ref = await (async () => { try { const r = await fetch("/datos/aves-estado-ar.json", {cache: "no-store"}); return r.ok ? await r.json() : null; } catch(e){ return null; } })();
    const lista = viewSpecies();
    if (ref && Array.isArray(ref.datos) && lista.length){
      const key = t => String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
      // se busca por el nombre actual (AviList) y, si no, por el que usa la resolución de 2017
      const idx = new Map(); ref.datos.forEach(d => { if (!idx.has(key(d[0]))) idx.set(key(d[0]), d); });  // si varios nombres de la resolución se fusionan en uno, vale el primero
      ref.datos.forEach(d => { if (d[5] && !idx.has(key(d[5]))) idx.set(key(d[5]), d); });
      const sh = new XSheet("6 Estado de conservación"); sheets.push(sh);
      header(sh, "Estado de conservación nacional de las especies de la tabla");
      put(sh, 3, `Fuente: ${ref.fuente}.`);
      if (ref.fuente_complementaria) put(sh, 5, `Complemento: ${ref.fuente_complementaria}.`);
      if (ref.taxonomia) put(sh, 2, `Taxonomía (orden, familia y nombres): ${ref.taxonomia}.`);
      put(sh, 4, "Orden, familia y estado no intervienen en ningún cálculo. Se usa la nomenclatura actual de AviList; los nombres de la resolución de 2017 también se reconocen, y cuando difieren se indican en la nota.");
      ["Especie", "Orden", "Familia", "Estado de conservación (Argentina)", "Nota"].forEach((t, c) => sh.set(6, c, t, S.head));
      let r = 6, hit = 0;
      lista.forEach(sp => {
        let d = idx.get(key(sp.name)), nota = "";
        if (!d){ const p = key(sp.name).split(" "); if (p.length > 2){ d = idx.get(p.slice(0, 2).join(" ")); if (d) nota = "Coincide a nivel de especie. "; } }
        r++; if (d) hit++;
        sh.set(r, 0, sp.name, S.sp);
        sh.set(r, 1, d ? d[1] : "", S.txt); sh.set(r, 2, d ? d[2] : "", S.txt); sh.set(r, 3, d ? d[3] : "", S.txt);
        const viejo = d && d[5] && key(d[5]) !== key(sp.name) ? `Nombre en la resolución de 2017: ${d[5]}. ` : "";
        sh.set(r, 4, d ? (nota + viejo + d[4]).trim() : "Sin coincidencia en la resolución.", S.txt2);
      });
      put(sh, r + 2, `Con coincidencia: ${hit} de ${lista.length} especies.`);
      sh.freeze = [7, 1]; sh.widths = {0: 30, 1: 20, 2: 20, 3: 42, 4: 60};
    }
  } catch(e){ /* la hoja es un complemento: si algo falla, el resto del libro sale igual */ }
'''

def apply(s):
    if MARCA in s:                       # versión anterior del parche: se reemplaza el bloque
        i = s.index("  // 6 · Estado"); j = s.index(ANCLA)
        return s[:i] + JS + s[j:]
    assert s.count(ANCLA) == 1, "no encuentro el punto de inserción en buildExport"
    return s.replace(ANCLA, JS + ANCLA)

if __name__ == "__main__":
    p = Path(sys.argv[1]); t = p.read_text(encoding="utf-8"); n = apply(t)
    p.write_text(n, encoding="utf-8"); print(p, "ya tenía el parche" if n == t else "parcheado")
