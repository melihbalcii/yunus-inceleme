from __future__ import annotations

import json
import unittest

import numpy as np

from testler.yardim import GeciciKokTesti, ses
from sesli import site
from sesli import ses as S


def _mp3(saniye: float, kbps: int = 64) -> bytes:
    import lameenc
    e = lameenc.Encoder()
    e.set_bit_rate(kbps)
    e.set_in_sample_rate(S.SR)
    e.set_channels(1)
    e.set_quality(5)
    return e.encode((np.sin(np.arange(int(S.SR * saniye)) / 20) * 8000).astype(np.int16).tobytes()) + e.flush()


class CerceveTesti(unittest.TestCase):
    def test_id3_ve_cop_bayt_atlanir(self):
        veri = _mp3(2.0)
        id3 = b"ID3\x04\x00\x00\x00\x00\x00\x0a" + b"\x00" * 10
        a, b = site.cerceveler(veri), site.cerceveler(id3 + b"\x00\x01" + veri)
        self.assertEqual(len(a), len(b))
        self.assertAlmostEqual(sum(c.ornek / c.hz for c in a), 2.0, delta=0.1)

    def test_eksik_son_cerceve_alinmaz(self):
        veri = _mp3(1.0)
        tam = site.cerceveler(veri)
        self.assertEqual(len(site.cerceveler(veri[:-10])), len(tam) - 1)


class BolmeTesti(GeciciKokTesti):
    def test_esit_parcalar_ve_sure_korunur(self):
        veri = _mp3(30.0)
        sinir = len(veri) // 3 + 1
        sureler = site.bol(veri, self.kok / "p", sinir=sinir)
        dosyalar = sorted((self.kok / "p").glob("*.mp3"), key=lambda d: int(d.stem))
        self.assertIn(len(dosyalar), (3, 4))  # çerçeve boyları eşit değil: sınırı aşacaksa bir parça eklenir
        self.assertEqual([d.name for d in dosyalar], [f"{i}.mp3" for i in range(1, len(dosyalar) + 1)])
        self.assertTrue(all(d.stat().st_size <= sinir for d in dosyalar))
        self.assertEqual(sum(d.stat().st_size for d in dosyalar), sum(c.uzunluk for c in site.cerceveler(veri)))
        self.assertAlmostEqual(sum(sureler), sum(c.ornek / c.hz for c in site.cerceveler(veri)), places=2)

    def test_cercevesiz_veri_hata(self):
        with self.assertRaises(site.SiteHatasi):
            site.bol(b"\x00" * 1000, self.kok / "p")


class YayinTesti(GeciciKokTesti):
    def kur(self):
        (self.y.kitaplik / "public").mkdir(parents=True)
        (self.y.kitaplik / "public" / "index.html").write_text("<html>")
        (self.y.kitaplik / "tanitim.json").write_text(json.dumps({"eser": {"kisa-oyku": "Tanıtım"}, "yazar": {}}))
        (self.y.kitaplik / ".env").write_text("WHATSAPP=905550000000\n")
        self.y.plan_csv.write_text("No,Köken,Ülke\n1,Rus,Rusya\n", encoding="utf-8")
        k = self.y.teslim / "Gemini 3.8 Flash"
        k.mkdir()
        S.mp3_yaz(k / "01 - Kısa Öykü - Yazar Bir.mp3", ses(3.0))
        (self.y.teslim / "Gemini 3.8 Live").mkdir()
        (self.y.teslim / "Gemini 3.8 Live" / "02 - Uzun Roman - Yazar İki.mp3").write_bytes(b"x")
        self.metin_yaz("uzun-roman", ["uzun roman metni"])

    def test_yayin_hazirlanir_kuru_calisma_ayni_sonucu_verir(self):
        self.kur()
        katalog, yakinda = site.hazirla(self.y, bildir=lambda s: None)
        self.assertEqual([k["id"] for k in katalog], ["kisa-oyku"])
        k = katalog[0]
        self.assertEqual((k["koken"], k["ulke"], k["ses"], k["tanitim"]), ("Rus", "Rusya", "Fola", "Tanıtım"))
        self.assertAlmostEqual(k["sure"], 3, delta=1)
        self.assertEqual([x["id"] for x in yakinda["yakinda"]], ["uzun-roman"])  # Live kaydı teslim sayılmaz
        self.assertEqual(yakinda["whatsapp"], "905550000000")
        self.assertTrue((self.y.yayin / "index.html").exists())
        self.assertEqual(json.loads((self.y.yayin / "katalog.json").read_text()), katalog)
        self.assertEqual(site.hazirla(self.y, bildir=lambda s: None, kuru=True), (katalog, yakinda))

    def test_kuru_calisma_hazir_olmayani_bildirir_hicbir_sey_yazmaz(self):
        self.kur()
        mesajlar: list[str] = []
        katalog, _ = site.hazirla(self.y, bildir=mesajlar.append, kuru=True)
        self.assertEqual(katalog, [])
        self.assertTrue(any(m.startswith("kodlanacak") for m in mesajlar))
        self.assertFalse(self.y.yayin.exists())

    def test_degisen_eserin_eski_parcalari_kaldirilir(self):
        self.kur()
        site.hazirla(self.y, bildir=lambda s: None)
        eski = {p.name for p in (self.y.yayin / "ses").iterdir()}
        S.mp3_yaz(self.y.teslim / "Gemini 3.8 Flash" / "01 - Kısa Öykü - Yazar Bir.mp3", ses(4.0))
        site.hazirla(self.y, bildir=lambda s: None)
        yeni = {p.name for p in (self.y.yayin / "ses").iterdir()}
        self.assertEqual(len(yeni), 1)
        self.assertFalse(eski & yeni)


if __name__ == "__main__":
    unittest.main()
