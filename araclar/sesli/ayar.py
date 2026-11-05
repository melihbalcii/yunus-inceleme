"""`.env` dosyalarını okur. Değerler hiçbir zaman ekrana ya da günlüğe yazılmaz."""
from __future__ import annotations

from pathlib import Path


class AyarHatasi(RuntimeError):
    pass


def env_oku(dosya: Path) -> dict[str, str]:
    """KEY=değer satırları; boş satır ve # ile başlayan satır atlanır, değerin çevresindeki tırnaklar kaldırılır."""
    sonuc: dict[str, str] = {}
    if not dosya.exists():
        return sonuc
    for satir in (x.strip() for x in dosya.read_text(encoding="utf-8").splitlines()):
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        anahtar, deger = satir.split("=", 1)
        anahtar = anahtar.strip().removeprefix("export ").strip()
        deger = deger.strip()
        if len(deger) > 1 and deger[0] == deger[-1] and deger[0] in "\"'":
            deger = deger[1:-1]
        sonuc[anahtar] = deger
    return sonuc


def gerekli(dosya: Path, anahtar: str) -> str:
    deger = env_oku(dosya).get(anahtar, "")
    if not deger:
        raise AyarHatasi(f"{dosya} içinde {anahtar} yok")
    return deger
