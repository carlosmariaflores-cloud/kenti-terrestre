"""Prueba de extremo a extremo del módulo de análisis global de Kenti Terrestre.
Genera una campaña simulada (10 sitios, 5 grupos terrestres) en .xlsx, la carga en
/g/global/ con un navegador real y compara cada resultado con numpy/scipy."""
import json, sys, itertools, numpy as np, openpyxl
from pathlib import Path
from scipy import stats
from pyproj import Transformer
from playwright.sync_api import sync_playwright
SEED = 20261006; rng = np.random.default_rng(SEED)
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
URL = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:47850/g/global/"
SITES = [f"TE-{i:02d}" for i in range(1, 11)]
ENV = ["Vega","Vega","Tolar","Tolar","Pajonal","Pajonal","Bosque","Bosque","Tolar","Pajonal"]
ROL = ["Referencia","Referencia","Influencia","Influencia","Influencia","Control","Control","Referencia","Influencia","Control"]
# alias: cómo escribe cada planilla a cada sitio
def spell(g, code):
    n = int(code[3:])
    return {"flora": code, "orn": f"te{n:02d}", "masto": f"TE-{n}", "herp": f"TE {n:02d}", "ento": f"Sitio {code}"}[g]
def counts(nt, n_sites, mu_scale):
    hab = rng.gamma(2.0, 1.0, size=(nt, 3))             # preferencia por tipo de ambiente
    out = np.zeros((nt, n_sites), int)
    for j in range(n_sites):
        e = {"Vega":0,"Tolar":1,"Pajonal":2,"Bosque":0}[ENV[j]]
        mu = mu_scale * hab[:, e] * rng.gamma(3.0, 1/3.0, size=nt)
        p = 3.0 / (3.0 + mu); out[:, j] = rng.negative_binomial(3.0, p)
    return out
G = {  # id: (archivo, nombre de hoja, taxones, sitios presentes, medida, familia?)
 "flora": ("flora-campania.xlsx", 30, SITES, "individuos", 3.0),
 "orn":   ("ornitologia-campania.xlsx", 25, SITES, "individuos", 4.0),
 "masto": ("mastozoologia-campania.xlsx", 12, SITES[:8], "registros independientes", 2.0),
 "herp":  ("herpetologia-campania.xlsx", 10, SITES, "individuos", 2.0),
 "ento":  ("entomologia-campania.xlsx", 40, SITES, "individuos", 6.0),
}
M = {}; 
for g, (fn, nt, ss, medida, sc) in G.items():
    C = counts(nt, len(ss), sc).astype(float)
    taxa = [f"{g}_taxon_{k+1:02d}" for k in range(nt)]
    M[g] = {"taxa": taxa, "sites": ss, "C": C, "medida": medida, "fn": fn}
M["ento"]["C"][5, 2] = np.nan                  # una celda 's/d'
M["herp"]["estado"] = {s: ("no_aplicable" if s == "TE-04" else "relevado") for s in SITES}
for g, d in M.items():
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Matriz"
    ws.append([f"Kenti · {g} · campaña simulada"]); ws.append([])
    extra = g == "orn"
    head = ["Especie", "Familia"] + [spell(g, s) for s in d["sites"]] + (["Parcela extra"] if extra else []) + ["Total"]
    ws.append(head)
    for k, t in enumerate(d["taxa"]):
        row = [t, f"Fam{k%7}"] + ["s/d" if np.isnan(v) else int(v) for v in d["C"][k]] + ([1] if extra else [])
        row.append(float(np.nansum(d["C"][k]))); ws.append(row)
    if "estado" in d:
        ws.append(["Estado del sitio", ""] + [{"relevado":"Relevado","no_aplicable":"No aplicable"}[d["estado"][s]] for s in d["sites"]])
    ws.append(["Total", ""] + [float(np.nansum(d["C"][:, j])) for j in range(len(d["sites"]))])
    md = wb.create_sheet("Metadatos"); md.append(["Medida", d["medida"]]); md.append(["Grupo", g])
    wb.save(OUT / d["fn"])
# sitios con coordenadas: 6 en Gauss-Krüger faja 3, 4 en lat/lon
tr_fw = Transformer.from_crs("EPSG:4326", "EPSG:5345", always_xy=True)
tr_bw = Transformer.from_crs("EPSG:5345", "EPSG:4326", always_xy=True)
lat = -23.55 + rng.uniform(-0.15, 0.15, 10); lon = -66.85 + rng.uniform(-0.15, 0.15, 10)
sites_js = []
for i, s in enumerate(SITES):
    d = {"codigo": s, "nombre": f"{ENV[i]} {i+1}", "componente": "Terrestre", "rol": ROL[i], "ambiente": ENV[i], "altitud": 3900 + 20*i, "alias": ""}
    if i < 6:
        e, n = tr_fw.transform(lon[i], lat[i]); d.update(este=round(e, 1), norte=round(n, 1), faja="3")
    else: d.update(lat=float(lat[i]), lon=float(lon[i]))
    sites_js.append(d)
# nombres de las planillas -> alias: sólo los que no coinciden con el código lo necesitan
for d in sites_js:
    n = int(d["codigo"][3:]); d["alias"] = ";".join([f"te{n:02d}", f"TE {n:02d}", f"Sitio {d['codigo']}"])

def alpha_ref(v):
    v = np.array([x for x in v if not np.isnan(x) and x > 0]); N = v.sum(); S = len(v)
    if S == 0: return dict(S=0, N=0, H=None, D1=None, J=None)
    p = v / N; H = -(p*np.log(p)).sum(); return dict(S=S, N=N, H=H, D1=1-(p*p).sum(), J=(H/np.log(S) if S > 1 else None))
def vec(g, s):
    d = M[g]; 
    if s not in d["sites"]: return None
    return d["C"][:, d["sites"].index(s)]
def est(g, s):
    if s not in M[g]["sites"]: return "no_relevado"
    return M[g].get("estado", {}).get(s, "relevado")
def sim(f, a, b):
    a = np.nan_to_num(a); b = np.nan_to_num(b)
    if f == "bc": return 2*np.minimum(a, b).sum()/(a.sum()+b.sum())
    if f == "jac": A, B = a > 0, b > 0; return (A&B).sum()/(A|B).sum()
    if f == "mh":
        Na, Nb = a.sum(), b.sum(); return 2*(a*b).sum()/(((a*a).sum()/Na**2 + (b*b).sum()/Nb**2)*Na*Nb)
res = {"seed": SEED}
with sync_playwright() as p:
    br = p.chromium.launch(); pg = br.new_page(viewport={"width":1400,"height":900})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(600)
    pg.evaluate("""(sj) => { state = vacio(); state.proyecto = {nombre:'Campaña simulada', campania:'2026-10'}; 
        state.sitios = sj.map((s,i) => ({id:'s'+i, obs:'', ...s})); save(); renderTab('sit'); }""", sites_js)
    pg.click('button[data-tab="ent"]')
    pg.set_input_files("#ent-file", [str(OUT / d["fn"]) for d in M.values()])
    done = 0
    for _ in range(200):
        pg.wait_for_timeout(150)
        if pg.evaluate("document.querySelector('#dlg-ent').open"):
            pg.click("#ent-ok"); done += 1
            if done == 5: break
    pg.wait_for_timeout(500)
    # columnas sin sitio: como lo haría el usuario, se eligen en la lista (queda guardado como alias)
    pre = pg.evaluate("() => state.entregas.map(e => ({g:e.grupo, sin_sitio:e.matrix.sites.filter((_,j)=>!e.siteMap[j])}))")
    res["columnas_sin_sitio_antes"] = pre
    for en_id, col, lbl in pg.evaluate("() => state.entregas.flatMap(e => e.matrix.sites.map((l,j)=>[e.id,j,l]).filter(([id,j,l])=>!e.siteMap[j]))"):
        import re
        m = re.fullmatch(r"TE-(\d+)", lbl)
        if m:
            pg.select_option(f'select[data-en="{en_id}"][data-col="{col}"]', label=None, value=f"s{int(m.group(1))-1}")
            pg.wait_for_timeout(100)
    info = pg.evaluate("""() => state.entregas.map(e => ({g:e.grupo, taxa:e.matrix.taxa.length, sites:e.matrix.sites.length, unmatched:e.siteMap.filter(x=>!x).length, medida:e.medida, hoja:e.hoja, estado:e.matrix.estado}))""")
    res["entregas"] = info
    # --- coordenadas ---
    ll = pg.evaluate("() => state.sitios.map(s => { const r = siteLatLon(s); return r ? [r.lat, r.lon, r.src||null] : null; })")
    dif = []
    for i, r in enumerate(ll):
        dif.append(max(abs(r[0]-lat[i]), abs(r[1]-lon[i])))
    res["coord_max_dif_grados"] = max(dif); res["coord_gk_sitios"] = 6
    # --- índices alfa ---
    cells = pg.evaluate("""() => { const o = {}; for (const s of state.sitios) for (const g of ['flora','herp','orn','masto','ento']) for (const k of ['S','N','H','D1','J']) { const r = cellIdx(s, g, k); o[s.codigo+'|'+g+'|'+k] = [r.v, r.why||'']; } return o; }""")
    mx = {k: 0.0 for k in ["S","N","H","D1","J"]}; ncell = 0; nmis = 0; n_na = 0
    for s in SITES:
        for g in G:
            e = est(g, s)
            for k in mx:
                v, why = cells[f"{s}|{g}|{k}"]
                if e != "relevado":
                    n_na += (k == "S")
                    if v is not None: nmis += 1
                    continue
                r = alpha_ref(vec(g, s))[k]
                if v is None and r is not None: print("FALTA", s, g, k, why, est(g,s)); continue
                if r is None: nmis += (v is not None); continue
                mx[k] = max(mx[k], abs(v - r)); ncell += 1
    res["alfa_max_dif"] = mx; res["alfa_celdas_comparadas"] = ncell//5; res["alfa_celdas_no_relevadas"] = int(n_na); res["alfa_inconsistencias_estado"] = nmis
    # --- beta ---
    beta = {}
    for g in G:
        for f in ("bc","jac","mh"):
            r = pg.evaluate("([g,f]) => { const b = betaFor('ter', g, f); return b ? {names:b.names, M:b.M} : null }", [g, f])
            ss = [s for s in SITES if est(g, s) == "relevado"]
            assert r["names"] == ss, (g, r["names"], ss)
            ref = np.array([[1 if i == j else sim(f, vec(g, a), vec(g, b)) for j, b in enumerate(ss)] for i, a in enumerate(ss)])
            beta[f"{g}|{f}"] = float(np.nanmax(np.abs(np.array(r["M"], float) - ref)))
    res["beta_max_dif"] = max(beta.values()); res["beta_matrices"] = len(beta)
    # --- concordancia ---
    pairs = pg.evaluate("""() => { const gs = gruposDe('ter').filter(g => entregaDe(g.id)), ss = sitesFor('ter'), out = [];
        for (let i=0;i<gs.length;i++) for (let j=i+1;j<gs.length;j++){ const x=[],y=[]; for (const s of ss){ const a=cellIdx(s,gs[i].id,'S'), b=cellIdx(s,gs[j].id,'S'); if (a.v!=null&&b.v!=null){x.push(a.v);y.push(b.v);} }
          if (x.length>=5){ const sp=spearman(x,y); out.push({a:gs[i].id,b:gs[j].id,rho:sp.rho,n:sp.n,p:sp.p}); } }
        const q = benjaminiHochberg(out.map(p=>p.p)); out.forEach((p,k)=>p.q=q[k]); return out; }""")
    dr = dp = dq = 0; ref_p = []
    for pr in pairs:
        x, y = [], []
        for s in SITES:
            if est(pr["a"], s) == "relevado" and est(pr["b"], s) == "relevado":
                x.append(alpha_ref(vec(pr["a"], s))["S"]); y.append(alpha_ref(vec(pr["b"], s))["S"])
        sp = stats.spearmanr(x, y); dr = max(dr, abs(sp.statistic - pr["rho"])); dp = max(dp, abs(sp.pvalue - pr["p"])); ref_p.append(sp.pvalue); assert len(x) == pr["n"]
    q = stats.false_discovery_control(ref_p, method="bh"); dq = max(abs(a - b["q"]) for a, b in zip(q, pairs))
    res["spearman_pares"] = len(pairs); res["spearman_max_dif"] = {"rho": dr, "p": dp, "p_BH": dq}
    # --- estados deducidos ---
    st = pg.evaluate("""() => { const o = {}; for (const s of state.sitios) for (const g of ['flora','herp','orn','masto','ento']) o[s.codigo+'|'+g] = estadoDe(s,g).e; return o; }""")
    bad = [k for k, v in st.items() if v != est(k.split('|')[1], k.split('|')[0])]
    res["estados_inconsistentes"] = bad; res["estados"] = st; res["S_por_celda"] = {k: v[0] for k, v in cells.items() if k.endswith("|S")}
    # --- exportaciones ---
    pg.click('button[data-tab="map"]'); pg.wait_for_timeout(300)
    with pg.expect_download() as dl: pg.click("#btn-kmz")
    kmz = OUT / "campania.kmz"; dl.value.save_as(str(kmz))
    import os, glob, time
    carpeta = pg.evaluate("() => appInfo && appInfo.carpeta")
    pg.click("#btn-export"); time.sleep(2.0)
    cand = sorted(glob.glob(os.path.join(carpeta, "*.xlsx")), key=os.path.getmtime) if carpeta else []
    xl = Path(cand[-1]) if cand else None
    import zipfile, xml.dom.minidom as md_
    z = zipfile.ZipFile(kmz); kml = md_.parseString(z.read("doc.kml")); res["kmz_placemarks"] = len(kml.getElementsByTagName("Placemark"))
    wb = openpyxl.load_workbook(xl) if xl else None; res["excel_hojas"] = len(wb.sheetnames) if wb else None; res["excel_en_carpeta_de_la_especialidad"] = carpeta
    res["errores_consola"] = errs
    br.close()
print(json.dumps(res, indent=1, default=float))
json.dump(res, open(OUT / "resultado.json", "w"), indent=1, default=float)
