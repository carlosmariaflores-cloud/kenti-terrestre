"""Simulaciones que respaldan el artículo de Kenti Terrestre.
A) 200 campañas aleatorias por el pipeline real del análisis global (lectura de matriz, sitios, alias, estados, índices, β, concordancia) vs NumPy/SciPy.
B) Sesgo de tratar sitios no relevados / no aplicables como ceros (frente al modelo de estados).
C) Error de tipo I y potencia del procedimiento de concordancia (Spearman + Benjamini-Hochberg) tal como está implementado."""
import json, sys, re, numpy as np
from scipy import stats
from playwright.sync_api import sync_playwright
OUT = sys.argv[1]; URL = "http://127.0.0.1:47850/g/global/"
SEED = 20261007; rng = np.random.default_rng(SEED)
GR = ["flora", "orn", "masto", "herp", "ento"]
STY = [lambda n: f"TE-{n:02d}", lambda n: f"te{n:02d}", lambda n: f"TE-{n}", lambda n: f"TE {n:02d}", lambda n: f"Sitio TE-{n:02d}"]
def alpha_ref(v):
    v = np.array([x for x in v if x is not None and not np.isnan(x) and x > 0]); N = v.sum(); S = len(v)
    if S == 0: return dict(S=0, N=0, H=None, D1=None, J=None)
    p = v/N; H = -(p*np.log(p)).sum(); return dict(S=S, N=N, H=H, D1=1-(p*p).sum(), J=(H/np.log(S) if S > 1 else None))
def sim(f, a, b):
    a = np.nan_to_num(a); b = np.nan_to_num(b)
    if f == "bc": return 2*np.minimum(a, b).sum()/(a.sum()+b.sum())
    if f == "jac": A, B = a > 0, b > 0; return (A&B).sum()/(A|B).sum()
    Na, Nb = a.sum(), b.sum(); return 2*(a*b).sum()/(((a*a).sum()/Na**2 + (b*b).sum()/Nb**2)*Na*Nb)
res = {"semilla": SEED}
# ------------------------------------------------------------------ A
def campaign():
    ns = int(rng.integers(6, 16)); sites = [f"TE-{i:02d}" for i in range(1, ns+1)]
    deliv = [g for g in GR if rng.random() < 0.9] or ["flora", "orn", "ento"]
    C = {}
    for g in deliv:
        k = int(rng.integers(max(5, ns-4), ns+1)); sv = sorted(rng.choice(ns, k, replace=False)); nt = int(rng.integers(8, 41))
        mu = rng.gamma(1.2, 3.0, size=(nt, 1)) * rng.gamma(3, 1/3, size=(nt, k)); M = rng.negative_binomial(2.0, 2.0/(2.0+mu)).astype(float)
        na_cells = []
        if rng.random() < 0.3: na_cells = [(int(rng.integers(nt)), int(rng.integers(k)))]
        for (i, j) in na_cells: M[i, j] = np.nan
        sty = int(rng.integers(5)); est = {}
        if rng.random() < 0.4 and k > 5:
            for j in rng.choice(k, int(rng.integers(1, 3)), replace=False): est[int(j)] = "no_aplicable"
        C[g] = dict(sv=[int(x) for x in sv], M=M, sty=sty, est=est, taxa=[f"{g}_{t}" for t in range(nt)], pres=bool(rng.random() < 0.15))
    return ns, sites, C
def rows_of(C_g, sites):
    sv = C_g["sv"]; M = C_g["M"]; sty = C_g["sty"]
    head = ["Especie", "Familia"] + [STY[sty](s+1) for s in sv] + ["Total"]
    rows = [["Campaña simulada"], [], head]
    for i, t in enumerate(C_g["taxa"]):
        r = [t, "F"]
        for j in range(len(sv)):
            v = M[i, j]
            r.append("s/d" if np.isnan(v) else ("x" if (C_g["pres"] and v > 0 and False) else (int(v) if v != 0 or rng.random() < 0.5 else "")))
        r.append(float(np.nansum(M[i]))); rows.append(r)
    if C_g["est"]: rows.append(["Estado del sitio", ""] + [("No aplicable" if C_g["est"].get(j) else "Relevado") for j in range(len(sv))] + [""])
    rows.append(["Total", ""] + [float(np.nansum(M[:, j])) for j in range(len(sv))] + [""])
    return rows
with sync_playwright() as p:
    br = p.chromium.launch(); pg = br.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(500)
    NC = 200; agg = dict(S=0.0, N=0.0, H=0.0, D1=0.0, J=0.0, beta=0.0, rho=0.0, p=0.0, q=0.0); n_cells = n_beta = n_pairs = n_state_bad = n_unmatched = n_cols = 0; n_hdr_bad = n_groups = n_camp_bad = 0
    for c in range(NC):
        ns, sites, C = campaign()
        sj = [{"codigo": s, "nombre": s, "componente": "Terrestre", "rol": "", "ambiente": "", "alias": ";".join(STY[k](i+1) for k in range(5))} for i, s in enumerate(sites)]
        ent = [{"g": g, "rows": rows_of(C[g], sites)} for g in C]
        out = pg.evaluate("""([sj, ent]) => { state = vacio(); state.sitios = sj.map((s,i) => ({id:'s'+i, obs:'', ...s})); state.entregas = [];
          for (const e of ent) { const matrix = parseMatrix(e.rows); const en = {id: uid(), grupo: e.g, archivo:'sim', hoja:'', fecha:'', medida:'individuos', matrix, fq:null};
            en.siteMap = matrix.sites.map(l => { const s = matchSite(l); return s ? s.id : null; }); addEntrega(en); }
          const O = {hdr: state.entregas.map(e=>e.matrix.headerRow), unmL: state.entregas.map(e=>[e.grupo, e.matrix.sites.filter((_,j)=>!e.siteMap[j]), e.matrix.sites.length, e.matrix.estado]), unm: state.entregas.reduce((t,e)=>t+e.siteMap.filter(x=>!x).length,0), cols: state.entregas.reduce((t,e)=>t+e.siteMap.length,0), cells:{}, est:{}, beta:{}, pairs:[]};
          for (const s of state.sitios) for (const g of ['flora','herp','orn','masto','ento']) { O.est[s.codigo+'|'+g] = estadoDe(s,g).e; for (const k of ['S','N','H','D1','J']) O.cells[s.codigo+'|'+g+'|'+k] = cellIdx(s,g,k).v; }
          for (const g of state.entregas.map(e=>e.grupo)) for (const f of ['bc','jac','mh']) { const b = betaFor('ter', g, f); O.beta[g+'|'+f] = b ? {names:b.names, M:b.M} : null; }
          const gs = gruposDe('ter').filter(g => entregaDe(g.id)), ss = sitesFor('ter');
          for (let i=0;i<gs.length;i++) for (let j=i+1;j<gs.length;j++){ const x=[],y=[]; for (const s of ss){ const a=cellIdx(s,gs[i].id,'S'), b=cellIdx(s,gs[j].id,'S'); if (a.v!=null&&b.v!=null){x.push(a.v);y.push(b.v);} }
            if (x.length>=5){ const sp=spearman(x,y); if (sp) O.pairs.push({a:gs[i].id,b:gs[j].id,rho:sp.rho,n:sp.n,p:sp.p}); } }
          const q = benjaminiHochberg(O.pairs.map(p=>p.p)); O.pairs.forEach((p,k)=>p.q=q[k]); return O; }""", [sj, ent])
        bad_h = sum(1 for h in out["hdr"] if h != 2); n_hdr_bad += bad_h; n_groups += len(out["hdr"])
        if bad_h: n_camp_bad += 1; continue
        n_unmatched += out["unm"]; n_cols += out["cols"]
        def vec(g, s):
            j = C[g]["sv"].index(s) if s in C[g]["sv"] else None
            return None if j is None else C[g]["M"][:, j]
        def est(g, i):
            if g not in C: return "sin_entrega"
            if i not in C[g]["sv"]: return "no_relevado"
            return "no_aplicable" if C[g]["est"].get(C[g]["sv"].index(i)) else "relevado"
        for i, s in enumerate(sites):
            for g in GR:
                e = est(g, i)
                if out["est"][f"{s}|{g}"] != e: n_state_bad += 1; continue
                if e != "relevado": continue
                r = alpha_ref(vec(g, i)); n_cells += 1
                for k in ("S", "N", "H", "D1", "J"):
                    v = out["cells"][f"{s}|{g}|{k}"]
                    if r[k] is None: assert v is None, (k, v); continue
                    agg[k] = max(agg[k], abs(v - r[k]))
        for key, b in out["beta"].items():
            g, f = key.split("|"); ss = [i for i in range(ns) if est(g, i) == "relevado"]
            if len(ss) < 2: assert b is None; continue
            assert b["names"] == [sites[i] for i in ss]
            ref = np.array([[1 if x == y else sim(f, vec(g, x), vec(g, y)) for y in ss] for x in ss]); agg["beta"] = max(agg["beta"], float(np.nanmax(np.abs(np.array(b["M"], float) - ref)))); n_beta += 1
        refp = []
        for pr in out["pairs"]:
            x, y = [], []
            for i in range(ns):
                if est(pr["a"], i) == "relevado" and est(pr["b"], i) == "relevado": x.append(alpha_ref(vec(pr["a"], i))["S"]); y.append(alpha_ref(vec(pr["b"], i))["S"])
            sp = stats.spearmanr(x, y); assert len(x) == pr["n"]; refp.append(sp.pvalue)
            agg["rho"] = max(agg["rho"], abs(sp.statistic - pr["rho"])); agg["p"] = max(agg["p"], abs(sp.pvalue - pr["p"])); n_pairs += 1
        if refp:
            q = stats.false_discovery_control(refp, method="bh"); agg["q"] = max(agg["q"], max(abs(a - b["q"]) for a, b in zip(q, out["pairs"])))
    if len(sys.argv) > 2 and sys.argv[2] == "soloA": json.dump({"A": None}, open(f"{OUT}/_x.json","w"))
    res["A"] = dict(campanias=NC, matrices_con_encabezado_mal_detectado=n_hdr_bad, matrices=n_groups, campanias_con_error_de_lectura=n_camp_bad, celdas_relevadas=n_cells, matrices_beta=n_beta, pares_spearman=n_pairs, columnas=n_cols, columnas_sin_sitio=n_unmatched, estados_distintos=n_state_bad, max_dif=agg, errores_consola=errs)
    print("A", json.dumps(res["A"]))
    if len(sys.argv) > 2 and sys.argv[2] == "soloA": json.dump(res, open(f"{OUT}/simulaciones_A_previa.json","w"), indent=1); sys.exit()
    # ------------------------------------------------------------------ C (en la página: spearman + BH reales)
    def typeI(nsites, ng=5, reps=2000):
        Z = rng.poisson(rng.gamma(2, 3, size=(reps, ng, 1)), size=(reps, ng, nsites)).tolist()
        return pg.evaluate("""(Z) => { let anyq=0, anyp=0, pairsP=0, pairs=0; for (const camp of Z){ const P=[]; for (let i=0;i<camp.length;i++) for (let j=i+1;j<camp.length;j++){ const sp=spearman(camp[i],camp[j]); if (sp){ P.push(sp.p); pairs++; if (sp.p<0.05) pairsP++; } }
            const q=benjaminiHochberg(P); if (q.some(v=>v<0.05)) anyq++; if (P.some(v=>v<0.05)) anyp++; } return {anyq, anyp, pairsP, pairs, n:Z.length}; }""", Z)
    TI = {}
    for n in (5, 7, 10, 15, 25):
        r = typeI(n); TI[n] = dict(pares_p05=r["pairsP"]/r["pairs"], alguna_p05=r["anyp"]/r["n"], alguna_q05=r["anyq"]/r["n"])
    res["C_tipoI"] = TI; print("C tipo I", json.dumps(TI))
    # potencia: factor latente compartido
    def power(nsites, w, reps=1000, ng=5):
        lat = rng.normal(size=(reps, 1, nsites)); Z = rng.poisson(np.exp(1.6 + w*lat + np.sqrt(1-w**2)*rng.normal(size=(reps, ng, nsites))*0.5)).tolist()
        r = pg.evaluate("""(Z) => { let anyq=0; for (const camp of Z){ const P=[]; for (let i=0;i<camp.length;i++) for (let j=i+1;j<camp.length;j++){ const sp=spearman(camp[i],camp[j]); if (sp) P.push(sp.p); }
            const q=benjaminiHochberg(P); if (q.some(v=>v<0.05)) anyq++; } return anyq/Z.length; }""", Z); return r
    PW = {f"n={n}": {f"w={w}": power(n, w) for w in (0.0, 0.3, 0.5, 0.7, 0.9)} for n in (7, 10, 15, 25)}
    res["C_potencia"] = PW; print("C potencia", json.dumps(PW))
    br.close()
# ------------------------------------------------------------------ B (scipy)
def sesgo(frac_unsurv, frac_na, ns=10, ng=5, reps=3000, same_sites=True):
    bias_mean = []; fp_zero = fp_state = 0; tot = 0; bc_bias = []
    for _ in range(reps):
        # comunidades independientes entre grupos
        S = np.array([rng.poisson(rng.gamma(4, 5), size=ns) + 1 for _ in range(ng)], float)
        sites_out = np.zeros((ng, ns), bool)
        k_out = int(round(frac_unsurv*ns))
        common = rng.choice(ns, k_out, replace=False)           # sitios inaccesibles para todo el equipo
        for g in range(ng):
            sites_out[g, common if same_sites else rng.choice(ns, k_out, replace=False)] = True
        na = np.zeros((ng, ns), bool)
        if frac_na: na[3, rng.choice(ns, int(round(frac_na*ns)), replace=False)] = True; S[3, na[3]] = 0
        excl = sites_out | na
        truth = np.array([S[g, ~na[g]].mean() for g in range(ng)])   # promedio de lo que se relevó donde el grupo puede estar
        # estado: promedio sólo sobre relevados; ingenuo: ceros en no relevados y no aplicables
        state_mean = np.array([S[g, ~excl[g]].mean() for g in range(ng)])
        Z = np.where(excl, 0, S); naive_mean = Z.mean(axis=1)
        bias_mean.append(((naive_mean - truth)/truth).mean()*100)
        # concordancia entre grupos independientes
        for a in range(ng):
            for b in range(a+1, ng):
                ok = ~excl[a] & ~excl[b]
                if ok.sum() >= 5 and np.ptp(S[a, ok]) > 0 and np.ptp(S[b, ok]) > 0: fp_state += stats.spearmanr(S[a, ok], S[b, ok]).pvalue < 0.05
                if np.ptp(Z[a]) > 0 and np.ptp(Z[b]) > 0: fp_zero += stats.spearmanr(Z[a], Z[b]).pvalue < 0.05
                tot += 1
    return dict(sesgo_relativo_medio_pct=float(np.mean(bias_mean)), pares_p05_ceros=fp_zero/tot, pares_p05_estados=fp_state/tot)
B = {}
for fu in (0.0, 0.1, 0.2, 0.3, 0.4):
    B[f"no_relevados={fu}"] = sesgo(fu, 0.2)
res["B"] = B; print("B", json.dumps(B, indent=0))
json.dump(res, open(f"{OUT}/simulaciones.json", "w"), indent=1)
