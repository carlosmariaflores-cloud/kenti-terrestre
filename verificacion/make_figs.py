import json, sys, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
from scipy import stats
OUT = sys.argv[1]; R = json.load(open(f"{OUT}/resultado.json"))
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8})
# ---------- Figura 1: arquitectura ----------
fig, ax = plt.subplots(figsize=(7.2, 4.8)); ax.set_xlim(0, 100); ax.set_ylim(0, 70); ax.axis("off")
def box(x, y, w, h, t, fc="#ffffff", ec="#3d6b1c", fs=7):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2,rounding_size=1.2", fc=fc, ec=ec, lw=1.1))
    ax.text(x + w/2, y + h/2, t, ha="center", va="center", fontsize=fs)
def arrow(x1, y1, x2, y2, c="#465040"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", color=c, lw=1.0))
ax.add_patch(Rectangle((1, 1), 98, 68, fc="#f2f4ef", ec="#c3cab9", lw=1))
ax.text(3, 65, "Kenti Terrestre.exe  (one Go binary, standard library only)", fontsize=8.5, fontweight="bold", color="#18200f")
box(4, 48, 28, 12, "Local server\n127.0.0.1 only; Host,\nheader and origin checks", fc="#e2ecd5")
box(36, 48, 26, 12, "Start screen\n(choose a specialty\nor the global analysis)", fc="#e2ecd5")
box(66, 48, 30, 12, "Data folders\nDocuments\\Kenti Terrestre\\\n<group>\\ (JSON, backup, Excel)", fc="#e2ecd5")
ax.text(4, 23.2, "Specialist modules: one shared template + one configuration object (GROUP) per group", fontsize=6.8, color="#465040")
for i, m in enumerate(["Flora", "Birds", "Mammals", "Herpeto-\nfauna", "Entomo-\nlogy"]):
    box(4 + i*13.4, 28, 11.6, 11, m)
box(4, 8, 66, 12, "Shared template: tables, \u03b1-diversity, \u03b2-diversity (Jaccard, Bray\u2013Curtis,\nMorisita\u2013Horn), UPGMA, PCA, Excel export with live formulas", fc="#eaeee5", fs=6.8)
box(76, 8, 20, 31, "Global\nanalysis\n\nsite registry,\nmatrix\nrecognition,\nstates,\nconcordance,\nKMZ", fc="#f6efdc", ec="#8a6a0a", fs=6.8)
arrow(18, 48, 18, 40.5); arrow(49, 48, 49, 40.5); arrow(81, 48, 85, 40.5)
arrow(37, 28, 37, 20.5)
ax.annotate("", xy=(76, 14), xytext=(70.4, 14), arrowprops=dict(arrowstyle="<-", color="#8a6a0a", lw=1.0)); ax.text(73.2, 16.2, ".xlsx", fontsize=6.3, color="#8a6a0a", ha="center")
fig.savefig(f"{OUT}/fig1_arquitectura.png", dpi=300, bbox_inches="tight"); plt.close(fig)
# ---------- Figura 2: estados y concordancia ----------
sites = [f"TE-{i:02d}" for i in range(1, 11)]; gs = ["flora", "orn", "masto", "herp", "ento"]
lab = {"flora": "Flora", "orn": "Birds", "masto": "Mammals", "herp": "Herpetofauna", "ento": "Entomology"}
S = np.full((10, 5), np.nan); ST = [[None]*5 for _ in range(10)]
for i, s in enumerate(sites):
    for j, g in enumerate(gs):
        ST[i][j] = R["estados"][f"{s}|{g}"]; v = R["S_por_celda"][f"{s}|{g}|S"]
        if ST[i][j] == "relevado": S[i, j] = v
fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 3.9), gridspec_kw={"width_ratios": [1.15, 1]})
im = a.imshow(np.ma.masked_invalid(S), cmap="Greens", aspect="auto", vmin=0)
for i in range(10):
    for j in range(5):
        if ST[i][j] == "relevado": a.text(j, i, f"{int(S[i,j])}", ha="center", va="center", fontsize=7, color="white" if S[i,j] > np.nanmax(S)*0.6 else "#18200f")
        else:
            a.add_patch(Rectangle((j-.5, i-.5), 1, 1, fc="#eaeee5", ec="#c3cab9", hatch="////" if ST[i][j] == "no_aplicable" else "..", lw=0))
a.set_xticks(range(5)); a.set_xticklabels([lab[g] for g in gs], rotation=30, ha="right"); a.set_yticks(range(10)); a.set_yticklabels(sites)
a.set_title("a) Richness (S) and site state", fontsize=8, loc="left"); a.tick_params(length=0)
for sp in a.spines.values(): sp.set_visible(False)
a.add_patch(Rectangle((0, 0), 0, 0, fc="#eaeee5", ec="#8a8a8a", hatch="////", label="not applicable")); a.add_patch(Rectangle((0, 0), 0, 0, fc="#eaeee5", ec="#8a8a8a", hatch="..", label="not surveyed"))
a.legend(loc="upper center", bbox_to_anchor=(0.5, -0.28), ncol=2, frameon=False, fontsize=6.5)
rho = np.full((5, 5), np.nan); ps = np.full((5, 5), np.nan)
for i in range(5):
    for j in range(5):
        if i == j: rho[i, j] = 1; continue
        ok = [k for k in range(10) if not np.isnan(S[k, i]) and not np.isnan(S[k, j])]
        r = stats.spearmanr(S[ok, i], S[ok, j]); rho[i, j] = r.statistic; ps[i, j] = r.pvalue
iu = np.triu_indices(5, 1); q = stats.false_discovery_control(ps[iu], method="bh"); qm = np.full((5, 5), np.nan); qm[iu] = q
rho_m = np.ma.masked_array(rho, mask=np.eye(5, dtype=bool)); im2 = b.imshow(rho_m, cmap="RdBu_r", vmin=-1, vmax=1)
for i in range(5):
    for j in range(5):
        if i == j: continue
        t = f"{rho[i,j]:.2f}"; 
        if i < j and qm[i, j] < 0.05: t += "*"
        b.text(j, i, t, ha="center", va="center", fontsize=7)
b.set_xticks(range(5)); b.set_xticklabels([lab[g] for g in gs], rotation=30, ha="right"); b.set_yticks(range(5)); b.set_yticklabels([lab[g] for g in gs])
b.set_title("b) Spearman ρ between groups (S)", fontsize=8, loc="left"); b.tick_params(length=0)
fig.tight_layout(); fig.savefig(f"{OUT}/fig2_estados_concordancia.png", dpi=300, bbox_inches="tight"); plt.close(fig)
n_sig = int((q < 0.05).sum()); print("pares", len(q), "significativos BH<0.05:", n_sig, "rho range", np.nanmin(rho[iu]), np.nanmax(rho[iu]))
json.dump({"rho": rho[iu].tolist(), "q": q.tolist()}, open(f"{OUT}/rho.json", "w"))
