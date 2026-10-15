#!/usr/bin/env python3
"""Insectos: estimadores de riqueza y hoja de referencia ecológica.

1) Pestaña «Diversidad alfa»: tarjeta «Estimadores de riqueza» con
   · por sitio: S, N, singletons (f1), doubletons (f2), Chao 1 (corregido por sesgo) y completitud S / Chao 1;
   · sobre el conjunto de sitios (cada sitio es una unidad de muestreo): Chao 2, Jackknife 1 y 2 y la curva de
     acumulación esperada (Coleman, exacta, sin remuestreo).
   Todo sale de la tabla que ya se carga (individuos por taxón y sitio): no hace falta ningún dato nuevo.
2) Excel de descarga: hoja «6 Estimadores de riqueza» con lo mismo y la curva como imagen.
3) Excel de descarga: hoja «7 Referencia ecológica» (gremio trófico, recurso, conservación) tomada de
   launcher/web/datos/insectos-referencia.json. Sólo aparece si el archivo tiene datos y algún taxón de la
   tabla coincide; no interviene en ningún cálculo. Sin datos cargados, el libro sale sin esa hoja.

Uso: lo importa prep.py (apply(texto) -> texto); también corre solo sobre la página ya generada:
    python3 parches/insectos_extra.py launcher/web/g/insectos.html
"""
import sys
from pathlib import Path

MARCA = "/* estimadores de riqueza */"
ANCLA_FN = "function renderAlfa(){"
ANCLA_HTML = '<p class="foot" id="alfa-unit-note" hidden></p>'
ANCLA_REND = "  lastAlfa = rows;\n  drawAlfaCharts();"
ANCLA_EXP = "  return {blob: await workbookBlob(sheets, X, `${GROUP.nombre} · resultados`), name: M.file};"

HTML = '''<div class="card" id="estim-card">
      <div class="card-head">
        <div><h3>Estimadores de riqueza</h3><div class="sub">Cuántos taxones faltan por registrar, calculado con la misma tabla de individuos.</div></div>
        <button class="btn ghost" data-copy="estim">Copiar tabla para Excel</button>
      </div>
      <div class="tbl-wrap" id="estim-table"></div>
      <div class="tbl-wrap" id="estim-inc" style="margin-top:18px"></div>
      <div class="chart" id="estim-chart" style="margin-top:14px"></div>
      <p class="foot" id="estim-note"></p>
      <details class="formulas">
        <summary>Fórmulas</summary>
        <div class="formula-list">
          <div><span>Chao 1</span>S + (N − 1)/N · f<sub>1</sub>(f<sub>1</sub> − 1) / (2(f<sub>2</sub> + 1))</div>
          <div><span>Chao 2</span>S + (m − 1)/m · Q<sub>1</sub>(Q<sub>1</sub> − 1) / (2(Q<sub>2</sub> + 1))</div>
          <div><span>Jackknife 1</span>S + Q<sub>1</sub> (m − 1)/m</div>
          <div><span>Jackknife 2</span>S + Q<sub>1</sub>(2m − 3)/m − Q<sub>2</sub>(m − 2)² / (m(m − 1))</div>
          <div><span>Curva de acumulación</span>E(S<sub>k</sub>) = Σ<sub>i</sub> [1 − C(m − m<sub>i</sub>, k) / C(m, k)]</div>
        </div>
      </details>
    </div>
    '''

FN = r'''/* estimadores de riqueza */
// f1, f2: taxones con 1 y 2 individuos en el sitio. Q1, Q2: taxones presentes en 1 y 2 sitios. m: sitios del análisis.
function chao1(v){
  const N = v.reduce((a, b) => a + b, 0), S = v.filter(x => x > 0).length;
  const f1 = v.filter(x => x === 1).length, f2 = v.filter(x => x === 2).length;
  const ent = v.every(x => Number.isInteger(x));
  const est = (ent && N > 0) ? S + (N - 1) / N * f1 * (f1 - 1) / (2 * (f2 + 1)) : null;
  return {S, N, f1, f2, est, comp: est ? 100 * S / est : null, ent};
}
function incidencia(act, spp){
  const m = act.length, q = spp.map(sp => act.filter(s => cellVal(sp, s) > 0).length).filter(x => x > 0);
  const S = q.length, Q1 = q.filter(x => x === 1).length, Q2 = q.filter(x => x === 2).length;
  const out = {m, S, Q1, Q2, chao2: null, jack1: null, jack2: null, curva: []};
  if (m < 2 || !S) return out;
  out.chao2 = S + (m - 1) / m * Q1 * (Q1 - 1) / (2 * (Q2 + 1));
  out.jack1 = S + Q1 * (m - 1) / m;
  out.jack2 = Math.max(S, S + Q1 * (2 * m - 3) / m - Q2 * (m - 2) ** 2 / (m * (m - 1)));
  const P = q.map(() => 1);                       // probabilidad de que el taxón no aparezca en k sitios
  for (let k = 1; k <= m; k++){
    let e = 0;
    q.forEach((mi, i) => { P[i] *= Math.max(0, (m - mi - (k - 1)) / (m - (k - 1))); e += 1 - P[i]; });
    out.curva.push(e);
  }
  return out;
}
function acumSvg(W, inc){
  const H = 230, m = {l:46, r:14, t:18, b:40}, pw = W - m.l - m.r, ph = H - m.t - m.b, n = inc.curva.length;
  const top = Math.max(inc.chao2 || 0, inc.jack1 || 0, inc.S) * 1.05, ax = niceAxis(0, top, 5);
  const X = k => m.l + (n > 1 ? pw * (k - 1) / (n - 1) : pw / 2), Y = v => m.t + ph * (1 - (v - ax.lo) / (ax.hi - ax.lo));
  let s = `<svg xmlns="${NS}" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Curva de acumulación de taxones por sitio">`;
  s += `<g class="g-grid">`;
  for (let i = 0; i <= ax.n; i++){ const v = ax.lo + ax.step * i; s += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}"/>`; }
  s += `</g><line class="g-base" x1="${m.l}" x2="${W - m.r}" y1="${Y(ax.lo)}" y2="${Y(ax.lo)}"/>`;
  for (let i = 0; i <= ax.n; i++){ const v = ax.lo + ax.step * i; s += `<text class="t-tick" x="${m.l - 6}" y="${Y(v) + 4}" text-anchor="end">${fmt(v, stepDec(ax.step))}</text>`; }
  const stepX = Math.max(1, Math.ceil(n / 12));
  for (let k = 1; k <= n; k++) if (k === 1 || k === n || k % stepX === 0) s += `<text class="t-x" x="${X(k)}" y="${Y(ax.lo) + 17}" text-anchor="middle">${k}</text>`;
  s += `<text class="t-x" x="${m.l + pw/2}" y="${H - 6}" text-anchor="middle">Sitios acumulados</text>`;
  if (inc.chao2 != null) s += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(inc.chao2)}" y2="${Y(inc.chao2)}" style="stroke:var(--ink-2);stroke-width:1.2;stroke-dasharray:5 4"/><text class="t-tick" x="${W - m.r}" y="${Y(inc.chao2) - 5}" text-anchor="end">Chao 2 = ${fmt(inc.chao2, 1)}</text>`;
  s += `<path d="${inc.curva.map((v, i) => (i ? "L" : "M") + X(i + 1) + " " + Y(v)).join("")}" style="fill:none;stroke:var(--accent);stroke-width:2.2;stroke-linejoin:round"/>`;
  inc.curva.forEach((v, i) => { s += `<circle cx="${X(i + 1)}" cy="${Y(v)}" r="3.2" style="fill:var(--accent);stroke:none"/>`; });
  return s + `</svg>`;
}
function renderEstim(act){
  const card = $("#estim-card"); if (!card) return;
  const spp = viewSpecies();
  const filas = act.map(s => ({s, ...chao1(spp.map(sp => cellVal(sp, s)))}));
  const tot = chao1(spp.map(sp => act.reduce((t, s) => t + cellVal(sp, s), 0)));
  const inc = incidencia(act, spp);
  lastEstim = {filas, tot, inc};
  const f = (v, d) => v == null ? "—" : fmt(v, d);
  let t = `<table class="res"><thead><tr><th>Sitio</th><th><span class="sym">S</span>Riqueza</th><th><span class="sym">N</span>Individuos</th><th><span class="sym">f<sub>1</sub></span>Singletons</th><th><span class="sym">f<sub>2</sub></span>Doubletons</th><th><span class="sym">Chao 1</span>Estimado</th><th><span class="sym">S / Chao 1</span>Completitud (%)</th></tr></thead><tbody>`;
  filas.forEach(r => { t += `<tr><td><span class="code">${esc(r.s.code)}</span><span class="nm">${esc(r.s.name)}</span></td><td>${r.S}</td><td>${f(r.N, 0)}</td><td>${r.f1}</td><td>${r.f2}</td><td>${f(r.est, 1)}</td><td>${f(r.comp, 0)}</td></tr>`; });
  t += `<tr class="pooled"><td>Total (γ)</td><td>${tot.S}</td><td>${f(tot.N, 0)}</td><td>${tot.f1}</td><td>${tot.f2}</td><td>${f(tot.est, 1)}</td><td>${f(tot.comp, 0)}</td></tr></tbody></table>`;
  $("#estim-table").innerHTML = filas.length ? t : `<div class="empty">No hay sitios relevados.</div>`;
  const rows2 = [["Chao 2", inc.chao2], ["Jackknife 1", inc.jack1], ["Jackknife 2", inc.jack2]];
  $("#estim-inc").innerHTML = inc.m >= 2 ? `<table class="res"><thead><tr><th>Estimador (sitios como unidades de muestreo)</th><th>Estimado</th><th>Completitud (%)</th></tr></thead><tbody>${rows2.map(([n, v]) => `<tr><td>${n}</td><td>${f(v, 1)}</td><td>${f(v ? 100 * inc.S / v : null, 0)}</td></tr>`).join("")}<tr class="pooled"><td>Observado: S = ${inc.S} · m = ${inc.m} sitios · Q<sub>1</sub> = ${inc.Q1} · Q<sub>2</sub> = ${inc.Q2}</td><td></td><td></td></tr></tbody></table>` : `<div class="empty">Chao 2, Jackknife y la curva de acumulación necesitan al menos 2 sitios en el análisis.</div>`;
  $("#estim-chart").innerHTML = inc.m >= 2 ? acumSvg(Math.min(760, Math.max(420, ($("#estim-chart").clientWidth || 640))), inc) : "";
  $("#estim-note").textContent = "Los valores salen de individuos sumados por sitio (todas las trampas juntas), así que son estimaciones a escala de sitio y no de trampa. Los estimadores por sitio (Chao 1) necesitan conteos enteros; los que usan los sitios como unidades suponen que esos sitios son réplicas de un mismo conjunto de comunidades, y si los sitios son muy distintos entre sí el resultado es sólo orientativo. Jackknife 2 no baja de la riqueza observada.";
  $("[data-copy=estim]").onclick = async () => {
    const L = [["Sitio", "Nombre", "S", "N", "f1", "f2", "Chao 1", "Completitud (%)"].join("\t")];
    filas.forEach(r => L.push([r.s.code, r.s.name, r.S, r.N, r.f1, r.f2, r.est == null ? "" : fmt(r.est, 2), r.comp == null ? "" : fmt(r.comp, 1)].join("\t")));
    L.push(["Total (γ)", "", tot.S, tot.N, tot.f1, tot.f2, tot.est == null ? "" : fmt(tot.est, 2), tot.comp == null ? "" : fmt(tot.comp, 1)].join("\t"));
    if (inc.m >= 2) rows2.forEach(([n, v]) => L.push([n, "", "", "", "", "", v == null ? "" : fmt(v, 2), v ? fmt(100 * inc.S / v, 1) : ""].join("\t")));
    toast(await copyText(L.join("\n")) ? "Tabla copiada: pégala en Excel" : "No se pudo copiar desde el navegador");
  };
}
let lastEstim = null;
'''

EXP = r'''  // 6 · Estimadores de riqueza (sólo sobre la tabla ya cargada) y 7 · Referencia ecológica (opcional)
  try {
    const actE = activeSites().filter(s => s.code || s.name), sppE = viewSpecies();
    if (actE.length && sppE.length){
      const sh = new XSheet("6 Estimadores de riqueza"); sheets.push(sh);
      header(sh, "Estimadores de riqueza");
      put(sh, 3, `Sitios en el análisis: ${actE.length}. Cada sitio suma las trampas: los valores son individuos por taxón y sitio.`);
      put(sh, 4, "Chao 1 usa conteos enteros por sitio. Chao 2 y Jackknife consideran cada sitio como una unidad de muestreo y suponen que los sitios son réplicas de un mismo conjunto de comunidades; si son muy distintos entre sí, son sólo orientativos.");
      const filas = actE.map(s => ({s, ...chao1(sppE.map(sp => cellVal(sp, s)))}));
      const tot = chao1(sppE.map(sp => actE.reduce((t, s) => t + cellVal(sp, s), 0)));
      const inc = incidencia(actE, sppE);
      let r = 6;
      sh.row(r, 0, ["Sitio", "Nombre", "Riqueza (S)", NLAB(), "Singletons (f1)", "Doubletons (f2)", "Chao 1", "Completitud S / Chao 1 (%)"], [S.head, S.head, S.headR, S.headR, S.headR, S.headR, S.headR, S.headR]);
      filas.forEach(x => { r++; sh.set(r, 0, x.s.code, S.codeB); sh.set(r, 1, x.s.name, S.txt); sh.set(r, 2, x.S, S.gen); sh.set(r, 3, x.N, S.gen); sh.set(r, 4, x.f1, S.gen); sh.set(r, 5, x.f2, S.gen); sh.set(r, 6, x.est ?? "", S.d2); sh.set(r, 7, x.comp ?? "", S.p1); });
      r++; sh.set(r, 0, "Total (γ)", S.poolL); sh.set(r, 1, "Todos los sitios del análisis", S.poolL);
      [[tot.S, S.poolG], [tot.N, S.poolG], [tot.f1, S.poolG], [tot.f2, S.poolG], [tot.est ?? "", S.d2B], [tot.comp ?? "", S.d2B]].forEach(([v, st], j) => sh.set(r, 2 + j, v, st));
      if (inc.m >= 2){
        r += 2; sh.set(r, 0, "Sitios como unidades de muestreo", S.colB); r++;
        sh.row(r, 0, ["Estimador", "", "Estimado", "Completitud (%)"], [S.head, S.head, S.headR, S.headR]);
        [["Chao 2", inc.chao2], ["Jackknife 1", inc.jack1], ["Jackknife 2", inc.jack2]].forEach(([n, v]) => { r++; sh.set(r, 0, n, S.txt); sh.set(r, 2, v, S.d2); sh.set(r, 3, v ? 100 * inc.S / v : "", S.p1); });
        r++; put(sh, r, `Observado: S = ${inc.S} · m = ${inc.m} sitios · Q1 = ${inc.Q1} taxones en un solo sitio · Q2 = ${inc.Q2} en dos sitios. Jackknife 2 no baja de la riqueza observada.`);
        r += 2; sh.set(r, 0, "Curva de acumulación esperada (Coleman)", S.colB); r++;
        sh.row(r, 0, ["Sitios acumulados", "", "Taxones esperados"], [S.head, S.head, S.headR]);
        inc.curva.forEach((v, i) => { r++; sh.set(r, 0, i + 1, S.gen); sh.set(r, 2, v, S.d2); });
        const fg = await figure(withExportHost(640, h => { h.innerHTML = acumSvg(640, inc); }), {title: "Curva de acumulación de taxones", subtitle: `${inc.m} sitios · riqueza observada ${inc.S} · Chao 2 = ${fmt(inc.chao2, 1)}`});
        sh.img(6, 10, fg, "Curva de acumulación de taxones");
      }
      r += 2; put(sh, r, "Fórmulas", S.h2);
      [["Chao 1", "S + (N − 1)/N · f1(f1 − 1) / (2(f2 + 1))   (f1, f2: taxones con 1 y 2 individuos)"], ["Chao 2", "S + (m − 1)/m · Q1(Q1 − 1) / (2(Q2 + 1))   (Q1, Q2: taxones en 1 y 2 sitios; m: sitios)"], ["Jackknife 1", "S + Q1 (m − 1)/m"], ["Jackknife 2", "S + Q1(2m − 3)/m − Q2(m − 2)² / (m(m − 1))"], ["Curva", "E(Sk) = Σ [1 − C(m − mi, k) / C(m, k)]   (mi: sitios donde aparece el taxón i)"]]
        .forEach(([a, b]) => { r++; sh.set(r, 0, a, S.txt2); sh.set(r, 2, b, S.txt); });
      r += 2; put(sh, r, "Chao, A. 1984. Scand. J. Stat. 11: 265-270 · Chao, A. 1987. Biometrics 43: 783-791 · Burnham, K. P. y W. S. Overton. 1979. Ecology 60: 927-936 · Colwell, R. K. y J. A. Coddington. 1994. Phil. Trans. R. Soc. B 345: 101-118.");
      sh.freeze = [7, 1]; sh.widths = {0: 22, 1: 28, 2: 14, 3: 14, 4: 14, 5: 14, 6: 12, 7: 20};
    }
    const ref = await (async () => { try { const r = await fetch("/datos/insectos-referencia.json", {cache: "no-store"}); return r.ok ? await r.json() : null; } catch(e){ return null; } })();
    if (ref && Array.isArray(ref.datos) && ref.datos.length && sppE.length){
      const key = t => String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
      const idx = new Map(); ref.datos.forEach(d => { if (d && d[0] && !idx.has(key(d[0]))) idx.set(key(d[0]), d); });
      // se busca el nombre completo, luego género + epíteto y, por último, la primera palabra (género o familia)
      const hallar = nom => { const p = key(nom).split(" ");
        for (const [k, niv] of [[p.join(" "), ""], [p.slice(0, 2).join(" "), "especie"], [p[0], p.length > 1 && /(idae|inae|oidea)$/.test(p[0]) ? "familia" : "género"]]) if (k && idx.has(k)) return [idx.get(k), niv];
        return [null, ""]; };
      const hits = sppE.map(sp => [sp, ...hallar(sp.name)]);
      if (hits.some(h => h[1])){
        const sh = new XSheet("7 Referencia ecológica"); sheets.push(sh);
        header(sh, "Gremio, recurso y conservación de los taxones de la tabla");
        const fu = Array.isArray(ref.fuente) ? ref.fuente.join("; ") : ref.fuente;
        put(sh, 3, `Fuente: ${fu || "sin especificar"}.`);
        put(sh, 4, "Estos datos son una referencia y no intervienen en ningún cálculo. Se asignan por nombre del taxón, por género o por familia; la columna de nota indica el nivel de la coincidencia y la fuente de cada fila. Un taxón sin coincidencia queda sin dato.");
        ["Taxón", "Orden", "Familia", "Gremio trófico", "Recurso / dieta", "Conservación", "Nota y fuente"].forEach((t, c) => sh.set(6, c, t, S.head));
        let r = 6, n = 0;
        hits.forEach(([sp, d, niv]) => {
          r++; if (d) n++;
          sh.set(r, 0, sp.name, S.sp);
          [1, 2, 3, 4, 5].forEach(c => sh.set(r, c, d ? (d[c] || "") : "", S.txt));
          sh.set(r, 6, d ? [niv ? `Coincide a nivel de ${niv}.` : "", d[6] || "", d[7] ? `Fuente: ${d[7]}.` : ""].filter(Boolean).join(" ") : "Sin dato en la referencia.", S.txt2);
        });
        put(sh, r + 2, `Con dato: ${n} de ${sppE.length} taxones.`);
        sh.freeze = [7, 1]; sh.widths = {0: 28, 1: 18, 2: 18, 3: 22, 4: 30, 5: 26, 6: 60};
      }
    }
  } catch(e){ /* son complementos: si algo falla, el resto del libro sale igual */ }
'''


def apply(s):
    if MARCA in s:
        return s                         # ya parcheado (para rehacerlo, regenerar la página con prep.py)
    for a in (ANCLA_FN, ANCLA_HTML, ANCLA_REND, ANCLA_EXP):
        assert s.count(a) == 1, f"no encuentro el punto de inserción: {a[:40]}"
    s = s.replace(ANCLA_FN, FN + ANCLA_FN)
    s = s.replace(ANCLA_HTML, HTML + ANCLA_HTML)
    s = s.replace(ANCLA_REND, "  renderEstim(act);\n" + ANCLA_REND)
    s = s.replace(ANCLA_EXP, EXP + ANCLA_EXP)
    return s


if __name__ == "__main__":
    p = Path(sys.argv[1]); t = p.read_text(encoding="utf-8"); n = apply(t)
    p.write_text(n, encoding="utf-8"); print(p, "ya tenía el parche" if n == t else "parcheado")
