"""Testlerin ortak araçları: geçici proje kökü, örnek eser listesi, sahte TTS."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ARACLAR = Path(__file__).resolve().parents[1]
if str(ARACLAR) not in sys.path:
    sys.path.insert(0, str(ARACLAR))

import numpy as np  # noqa: E402

from sesli.yollar import Yollar  # noqa: E402

ORNEK_ESERLER = [
    {"ad": "kisa-oyku", "no": 1, "eser": "Kısa Öykü", "yazar": "Yazar Bir", "durum": "etkin", "yalniz_fola": True},
    {"ad": "uzun-roman", "no": 2, "eser": "Uzun Roman", "yazar": "Yazar İki", "durum": "etkin", "yalniz_fola": True},
    {"ad": "emel-eseri", "no": 3, "eser": "Emel Eseri", "yazar": "Yazar Üç", "durum": "etkin", "yalniz_fola": False},
    {"ad": "birakilan", "no": 4, "eser": "Bırakılan", "yazar": "Yazar Dört", "durum": "vazgecildi"},
]


class GeciciKokTesti(unittest.TestCase):
    """Her test için boş bir proje kökü; eser listesi ve metinler içine yazılır."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.kok = Path(self._td.name)
        self.y = Yollar.kok_altinda(self.kok)
        self.y.podcast.mkdir(parents=True)
        self.y.tmp.mkdir()
        self.y.parcalar.mkdir()
        self.y.teslim.mkdir()
        self.y.emel_teslim.mkdir()
        self.eser_listesi_yaz(ORNEK_ESERLER)

    def tearDown(self) -> None:
        self._td.cleanup()

    def eser_listesi_yaz(self, eserler: list[dict]) -> None:
        self.y.eserler.write_text(json.dumps({"eserler": eserler}, ensure_ascii=False), encoding="utf-8")

    def metin_yaz(self, ad: str, paragraflar: list[str]) -> Path:
        k = self.y.eser_klasoru(ad)
        k.mkdir(parents=True, exist_ok=True)
        d = k / "seslendirme-metni.txt"
        d.write_text("\n\n".join(paragraflar) + "\n", encoding="utf-8")
        return d


def ses(saniye: float, deger: float = 0.3) -> np.ndarray:
    from sesli.ses import SR
    return np.full(int(SR * saniye), deger, dtype=np.float32)


class SahteTTS:
    """Her metin için uzunluğuyla orantılı ses döndürür; istenirse sırayla verilen istisnaları fırlatır.
    `atilan`, gerçek istemcideki gibi kotayı harcamış olabilecek istekleri sayar (kota reddi saymaz)."""

    def __init__(self, hatalar: list[BaseException | None] | None = None, kr_sn: float = 15.0):
        self.istekler: list[str] = []
        self.butceler: list[int] = []
        self.atilan = 0
        self._hatalar = list(hatalar or [])
        self._kr_sn = kr_sn

    def uret(self, metin: str, en_cok: int = 2) -> np.ndarray:
        from sesli.gemini import KotaDoldu
        self.istekler.append(metin)
        self.butceler.append(en_cok)
        if self._hatalar:
            h = self._hatalar.pop(0)
            if h is not None:
                if not isinstance(h, KotaDoldu):
                    self.atilan += 1
                raise h
        self.atilan += 1
        return ses(max(0.5, len(metin) / self._kr_sn))
