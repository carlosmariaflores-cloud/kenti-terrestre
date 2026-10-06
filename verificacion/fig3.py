import json, sys, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
OUT = sys.argv[1]; R = json.load(open(f"{OUT}/simulaciones.json")); plt.rcParams.update({"font.size": 8})
fig, ax = plt.subplots(1, 3, figsize=(7.2, 2.7))
fr = [0, 10, 20, 30, 40]; B = [R["B"][f"no_relevados={x/100}"] for x in fr]
a = ax[0]; a.plot(fr, [b["pares_p05_ceros"]*100 for b in B], "o-", color="#b0381d", label="blanks as zeros"); a.plot(fr, [b["pares_p05_estados"]*100 for b in B], "s-", color="#3d6b1c", label="site states")
a.axhline(5, color="#888", ls=":", lw=1); a.set_xlabel("Sites not surveyed by the whole team (%)"); a.set_ylabel("Group pairs with p < 0.05 (%)"); a.set_title("a) Spurious correlations", fontsize=8, loc="left"); a.legend(frameon=False, fontsize=6.5)
b_ = ax[1]; b_.plot(fr, [b["sesgo_relativo_medio_pct"] for b in B], "o-", color="#b0381d"); b_.axhline(0, color="#888", lw=1); b_.set_xlabel("Sites not surveyed by the whole team (%)"); b_.set_ylabel("Bias of mean richness (%)"); b_.set_title("b) Bias of the cross-group mean", fontsize=8, loc="left")
c = ax[2]; ws = [0.0, 0.3, 0.5, 0.7, 0.9]
for n, col in zip((7, 10, 15, 25), ("#9ecb7a", "#6aa84f", "#3d6b1c", "#1d3a0c")): c.plot(ws, [R["C_potencia"][f"n={n}"][f"w={w}"]*100 for w in ws], "o-", color=col, label=f"n = {n} sites", ms=3)
c.axhline(5, color="#888", ls=":", lw=1); c.set_xlabel("Shared signal among groups (w)"); c.set_ylabel("Campaigns with ≥ 1 pair, BH q < 0.05 (%)"); c.set_title("c) Concordance test", fontsize=8, loc="left"); c.legend(frameon=False, fontsize=6.5)
for x in ax:
    for s in ("top", "right"): x.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(f"{OUT}/fig3_simulaciones.png", dpi=300, bbox_inches="tight")
