"""Rastgele hata sıralarıyla kota dayanıklılığı (kalite/HATA-DEFTERI.md H-001; yol haritası 2. adım).

Elle yazılan hata testleri ancak düşünülen senaryoyu sınar. Burada Hypothesis, Gemini'nin verebileceği yanıtların
(ses, boş yanıt, güvenlik reddi, bağlanamama, yanıt kaybı, sunucu hatası, dakikalık ve günlük sınır, başka istemci
hatası) rastgele sıralarını üretir. Her sırada iki şey denetlenir:

1. Hiçbir sırada bozulmaması gereken kurallar: aynı anda en çok bir istek; kotayı harcayabilecek istek bütçeyi
   aşmaz; her istek deftere tam bir kez yazılır; defterdeki harcayan istek sayısı `atilan` ile aynıdır.
2. Ayrı yazılmış küçük bir başvuru modeli: kod, her sırada modelin söylediği sonucu ve istek sayılarını birebir verir.
"""
from __future__ import annotations

import threading
import unittest
from dataclasses import dataclass

import httpx
from hypothesis import given, settings
from hypothesis import strategies as st

from sesli import gemini as G
from testler.test_gemini import _istemci_hatasi, _wav, _yanit

TURLER = ("ses", "bos", "guvenlik", "gitmedi", "zaman_asimi", "sunucu", "dakika", "gun", "istemci")
HARCAYAN = {"ses", "bos", "guvenlik", "zaman_asimi", "sunucu", "istemci"}   # kota harcanmış olabilir


def _davranis(tur: str) -> object:
    from google.genai import errors
    return {
        "ses": lambda: _yanit(_wav(0.05)),
        "bos": lambda: _yanit(None, sebep="OTHER"),
        "guvenlik": lambda: _yanit(None, sebep="SAFETY"),
        "gitmedi": lambda: httpx.ConnectError("bağlanılamadı"),
        "zaman_asimi": lambda: httpx.ReadTimeout("yanıt gelmedi"),
        "sunucu": lambda: errors.ServerError(503, {"error": {"code": 503, "message": "meşgul", "status": "X"}}),
        "dakika": lambda: _istemci_hatasi(429, "per minute limit, retry in 1s"),
        "gun": lambda: _istemci_hatasi(429, "GenerateRequestsPerDay limit"),
        "istemci": lambda: _istemci_hatasi(400, "geçersiz istek"),
    }[tur]()


class SiraliIstemci:
    """Sıradaki davranışı uygular; aynı anda kaç istek çalıştığını ölçer. Sıra biterse ses döner."""

    def __init__(self, sira: list[str]):
        self.sira = list(sira)
        self.models = self
        self.cagri = 0
        self.ayni_anda = 0
        self.en_cok_ayni_anda = 0
        self._kilit = threading.Lock()

    def generate_content(self, **_: object) -> object:
        with self._kilit:
            self.cagri += 1
            self.ayni_anda += 1
            self.en_cok_ayni_anda = max(self.en_cok_ayni_anda, self.ayni_anda)
            tur = self.sira.pop(0) if self.sira else "ses"
        try:
            d = _davranis(tur)
            if isinstance(d, BaseException):
                raise d
            return d
        finally:
            with self._kilit:
                self.ayni_anda -= 1


@dataclass
class Beklenen:
    sonuc: str      # "ses" ya da istisna sınıfının adı
    cagri: int      # Gemini'ye giden toplam istek
    atilan: int     # kotayı harcamış olabilecek istek


def model(sira: list[str], en_cok: int) -> Beklenen:
    """uret()'in sözleşmesi, koddan bağımsız yazıldı (gemini.py'deki sabitlerle)."""
    if en_cok < 1:
        return Beklenen("GeciciHata", 0, 0)
    gitmedi = dakika = kayip = cagri = atilan = 0
    sira = list(sira)
    while True:
        tur = sira.pop(0) if sira else "ses"
        cagri += 1
        if tur in HARCAYAN:
            atilan += 1
        if tur == "gitmedi":
            gitmedi += 1
            if gitmedi >= G.GITMEDI_DENEME:
                return Beklenen("GeciciHata", cagri, atilan)
        elif tur in ("zaman_asimi", "sunucu"):
            kayip += 1
            if kayip >= en_cok:
                return Beklenen("GeciciHata", cagri, atilan)
        elif tur == "dakika":
            dakika += 1
            if dakika >= G.DAKIKALIK_DENEME:
                return Beklenen("GeciciHata", cagri, atilan)
        else:
            sonuc = {"ses": "ses", "bos": "BosYanit", "guvenlik": "GuvenlikReddi", "gun": "KotaDoldu",
                     "istemci": "ClientError"}[tur]
            return Beklenen(sonuc, cagri, atilan)


class RastgeleHataSirasiTesti(unittest.TestCase):
    @settings(max_examples=400, deadline=None)
    @given(sira=st.lists(st.sampled_from(TURLER), max_size=14), en_cok=st.integers(min_value=0, max_value=4))
    def test_her_hata_sirasinda_kota_kurallari_korunur(self, sira: list[str], en_cok: int) -> None:
        istemci = SiraliIstemci(sira)
        defter: list[dict[str, object]] = []
        t = G.GeminiTTS(G.Arac("Deneme TTS", "deneme-model", "Fola"), "anahtar", bildir=lambda s: None,
                        uyu=lambda s: None, istemci_kur=lambda: istemci, defter=defter.append)
        try:
            t.uret("metin", en_cok=en_cok)
            sonuc = "ses"
        except Exception as h:  # noqa: BLE001 — sonucun türü modelle karşılaştırılır
            sonuc = type(h).__name__

        # 1. değişmez kurallar
        self.assertLessEqual(istemci.en_cok_ayni_anda, 1, "aynı anda iki istek")
        self.assertLessEqual(t.atilan, en_cok, "kota harcayan istek bütçeyi aştı")
        self.assertEqual(len(defter), istemci.cagri, "her istek deftere tam bir kez yazılmalı")
        harcayan = sum(1 for k in defter if k["sonuc"] not in ("gitmedi", "sinir"))
        self.assertEqual(harcayan, t.atilan, "defter ile sayaç uyuşmuyor")
        if sonuc == "ses":
            self.assertEqual([k["sonuc"] for k in defter].count("ses"), 1)
            self.assertEqual(defter[-1]["sonuc"], "ses")

        # 2. başvuru modeli
        self.assertEqual(Beklenen(sonuc, istemci.cagri, t.atilan), model(sira, en_cok))


if __name__ == "__main__":
    unittest.main()
