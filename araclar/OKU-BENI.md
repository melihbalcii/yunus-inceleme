# araclar/

| Klasör / dosya | Ne |
|---|---|
| `sesli_kitap.py` | Sesli kitap sisteminin tek giriş noktası (`--help`) |
| `sesli/` | Sistemin paketi; mimari, kurallar ve komutlar: [`sesli/MIMARI.md`](sesli/MIMARI.md) |
| `testler/` | Birim testleri ve gerçek veriyle uyumluluk testi |
| `eski/` | 5 Kasım 2026 öncesi betikler (çalıştırılmaz, başvuru için) |

```sh
.venv-ses/bin/python araclar/sesli_kitap.py durum
cd araclar && ../.venv-ses/bin/python -m unittest discover -s testler -t .
cd araclar && ../.venv-ses/bin/python -m mypy
```
