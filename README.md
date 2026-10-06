# Kenti Terrestre 0.1.1

Part of the Kenti family (see also https://github.com/carlosmariaflores-cloud/kenti, Kenti Libre).

Offline desktop application for terrestrial biodiversity monitoring: flora, birds, mammals, herpetofauna and entomology modules behind a start screen, plus a global-analysis module that consolidates the specialists' Excel books. One Go executable (standard library only); data stay on the user's computer in `Documents\Kenti Terrestre\<group>\`.

Described in: Flores, C. M. *Kenti Terrestre: an offline, configuration-driven desktop application for consolidating terrestrial biodiversity monitoring data from several taxonomic specialists* (manuscript).

## Contents

| Folder / file | What it is |
|---|---|
| `launcher/` | Go source (local server, per-group data folders, Windows/Linux platform code) and the embedded interfaces in `launcher/web/` |
| `prep.py`, `home.html` | Build step that turns the specialist-module pages into `launcher/web/g/<group>.html` (relative API paths, back bar, two corrections to the consolidator) and writes the start screen |
| `mkicon.py` | Generates the Windows icon resource (`.syso`) from `launcher/web/icono.png` |
| `verificacion/` | End-to-end test (`e2e_global.py`), simulation studies (`sims.py`), figure scripts and their results (`resultado.json`, `simulaciones.json`) |

## Build (Go 1.22 or later)

```sh
cd launcher
# Linux / macOS (testing)
go build -o kenti-terrestre .
# Windows
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath \
  -ldflags "-H windowsgui -s -w -X 'main.appID=kenti-terrestre' -X 'main.appName=Kenti Terrestre' -X 'main.folderName=Kenti Terrestre' -X 'main.portText=47850'" \
  -o "Kenti Terrestre.exe" .
```

`launcher/web/` is already generated and is embedded at build time. `prep.py` is documented for transparency; it needs the single-file pages of the stand-alone modules, which are not part of this repository.

## Reproduce the verification

Needs Python 3.11+ with `numpy`, `scipy`, `openpyxl`, `pyproj`, `playwright` (Chromium) and `matplotlib`.

```sh
KENTI_DOCS=/tmp/kenti-docs KENTI_NO_BROWSER=1 ./kenti-terrestre &   # serves http://127.0.0.1:47850/
python3 verificacion/e2e_global.py out/            # 10 sites × 5 groups, compared with NumPy/SciPy/pyproj
python3 verificacion/sims.py out/                  # studies A, B and C (takes several minutes)
python3 verificacion/make_figs.py out/ && python3 verificacion/fig3.py out/
```

## Licence

MIT, as the rest of this repository. The Kenti name and logo are excluded (trademark application pending, INPI Argentina).
