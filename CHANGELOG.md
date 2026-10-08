# Changelog

## Sin publicar
- Al exportar figuras, las fuentes (Public Sans, Source Serif 4, IBM Plex Mono) no se incrustaban en el SVG/PNG: la página las pedía con ruta relativa (`fuentes/…`), que bajo `/g/<id>/` daba 404, y el error se descartaba en silencio. Ahora la ruta es absoluta (`/fuentes/…`). Afecta a Flora, Aves, Mamíferos, Herpetofauna y Entomología; no cambia ningún cálculo ni el Excel. `prep.py` aplica la corrección al armar las páginas.

## 0.1.1 — 2026-10-06
- Versión publicada (DOI 10.5281/zenodo.23197949).
