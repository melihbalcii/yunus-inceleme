"""Okuma ölçüm kaydı (.tmp/fola-olcum.jsonl): her denemenin model, karakter, saniye, eşleşme bilgisi.
Planlama okuma hızını ve başarı oranını buradan öğrenir."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

VARSAYILAN_HIZ = 14.5  # kr/sn, ölçüm yoksa


def oku(dosya: Path) -> list[dict[str, Any]]:
    try:
        satirlar = dosya.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    sonuc = []
    for s in satirlar:
        if s.strip():
            try:
                sonuc.append(json.loads(s))
            except ValueError:
                continue  # yarım yazılmış satır bütün planlamayı durdurmasın
    return sonuc


def yaz(dosya: Path, model: str, **alanlar: object) -> None:
    satir = json.dumps(dict(zaman=time.strftime("%Y-%m-%d %H:%M"), model=model, **alanlar), ensure_ascii=False)
    try:
        with open(dosya, "a", encoding="utf-8") as f:
            f.write(satir + "\n")
    except OSError:
        pass


def model_hizi(dosya: Path, model: str) -> float:
    """Modelin son 40 başarılı ve bir dakikadan uzun denemesinin okuma hızı medyanı (kr/sn)."""
    h = sorted([x["kr"] / x["sn"] for x in oku(dosya)
                if x.get("model") == model and x.get("iyi") and x.get("sn", 0) > 60][-40:])
    return h[len(h) // 2] if len(h) >= 3 else VARSAYILAN_HIZ


def basari_orani(dosya: Path, model: str) -> float:
    son = [x for x in oku(dosya) if x.get("model") == model and not x.get("yama")][-40:]
    return sum(1 for x in son if x.get("iyi")) / len(son) if len(son) >= 5 else 0.8
