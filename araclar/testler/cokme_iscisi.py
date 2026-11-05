"""Çökme testinin işçisi (testler/test_cokme.py ayrı süreç olarak çalıştırır).

Bir bloğu sahte Gemini ile okur. COKME ortam değişkeninde adı verilen anda süreci os._exit ile öldürür: fişi çekmek
gibi, hiçbir `finally` ya da temizlik kodu çalışmaz. Her istek, sayılsın diye `istekler.log`'a diske yazılarak eklenir.

Kullanım: python -m testler.cokme_iscisi <kök> <metin dosyası>
Çıkış: 0 blok yazıldı · 3 bugün yeni istek atılmadı (GeciciHata) · 9 bilerek çökertildi
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

from sesli import ses as S
from sesli.gemini import GeciciHata
from sesli.okuma import OkumaAyari, Okuyucu
from sesli.yollar import Yollar

COKME = os.environ.get("COKME", "")


def _cok(an: str) -> None:
    if COKME == an:
        os._exit(9)


class DiskeSayanTTS:
    def __init__(self, defter: Path):
        self.defter = defter
        self.atilan = 0

    def uret(self, metin: str, en_cok: int = 2) -> np.ndarray:
        with open(self.defter, "a", encoding="utf-8") as f:
            f.write(f"{len(metin)}\n")
            f.flush()
            os.fsync(f.fileno())
        self.atilan += 1
        _cok("istek")            # istek gitti, kota harcandı, yanıt gelmeden süreç öldü
        return np.full(S.SR * 2, 0.3, dtype=np.float32)


def _olc(metin: str, ses: np.ndarray) -> tuple[float, list[str]]:
    _cok("olcum")                # yanıt geldi, Whisper ölçümü sürerken süreç öldü
    return 0.99, []


def main() -> int:
    kok, metin_dosyasi = Path(sys.argv[1]), Path(sys.argv[2])
    y = Yollar.kok_altinda(kok)
    y.parcalar.mkdir(parents=True, exist_ok=True)
    okuyucu = Okuyucu(DiskeSayanTTS(kok / "istekler.log"), OkumaAyari(model="deneme-model", ses="Fola"), y,
                      bildir=lambda s: None, olc=_olc, kalite=lambda ses: (4.0, 4.0),
                      yamala=lambda *a, **k: None, gun=lambda: "2026-11-06")
    try:
        okuyucu._blok(metin_dosyasi.read_text(encoding="utf-8"), "[1]")
    except GeciciHata:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
