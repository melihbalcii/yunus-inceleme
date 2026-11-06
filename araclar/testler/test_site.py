from __future__ import annotations

import datetime as dt
import json
import unittest
from unittest import mock

import numpy as np

from testler.yardim import ORNEK_ESERLER, GeciciKokTesti, ses
from sesli.durum import DurumDeposu
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


class YayinTabani(GeciciKokTesti):
    """Yayın testlerinin ortak kurulumu (test içermez)."""

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


class YayinTesti(YayinTabani):
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


class KatalogKaydiTesti(YayinTabani):
    """Sitenin gösterdiği her şey katalog.json ve yakinda.json'dan gelir: kayıtlar eksiksiz ve doğru olmalı."""

    def test_katalog_kaydi_eksiksiz(self):
        self.kur()
        (self.y.kitaplik / "tanitim.json").write_text(json.dumps(
            {"eser": {"kisa-oyku": "Tanıtım"}, "yazar": {"Yazar Bir": "Yazar hakkında"}}))
        (k,) = site.hazirla(self.y, bildir=lambda s: None)[0]
        bilgi = json.loads((self.y.yayin / k["yol"].lstrip("/") / "bilgi.json").read_text())
        mp3 = self.y.teslim / "Gemini 3.8 Flash" / "01 - Kısa Öykü - Yazar Bir.mp3"
        self.assertRegex(k["yol"], r"^/ses/kisa-oyku-[0-9a-f]{8}$")
        self.assertEqual({x: v for x, v in k.items() if x != "yol"}, {
            "id": "kisa-oyku", "no": 1, "eser": "Kısa Öykü", "yazar": "Yazar Bir", "koken": "Rus", "ulke": "Rusya",
            "sure": round(sum(bilgi["sureler"])), "boyut": bilgi["boyut"], "parcalar": bilgi["sureler"], "ses": "Fola",
            "tanitim": "Tanıtım", "yazarBilgi": "Yazar hakkında",
            "eklenme": dt.datetime.fromtimestamp(mp3.stat().st_mtime).strftime("%Y-%m-%dT%H:%M")})

    def test_3_1_ile_okunan_sulafat_2_5_flash_yayinlanmaz(self):
        for klasor, beklenen in (("Gemini 3.1 Flash", ["Sulafat"]), ("Gemini 3.8 Flash Lite", ["Fola"]),
                                 ("Gemini 2.5 Flash", [])):  # 2.5 Flash kayıtları ses kalitesi yüzünden yayınlanmaz
            with self.subTest(klasor=klasor):
                self.setUp()
                self.kur()
                (self.y.teslim / "Gemini 3.8 Flash").rename(self.y.teslim / klasor)
                self.assertEqual([k["ses"] for k in site.hazirla(self.y, bildir=lambda s: None)[0]], beklenen)

    def test_yakinda_rafi_okunani_once_gosterir(self):
        self.kur()
        self.eser_listesi_yaz(ORNEK_ESERLER + [
            {"ad": "ucuncu", "no": 5, "eser": "Üçüncü", "yazar": "Yazar Beş", "durum": "etkin", "yalniz_fola": True}])
        self.metin_yaz("ucuncu", ["kısa"])
        self.y.plan_csv.write_text("No,Köken,Ülke\n1,Rus,Rusya\n2,Fransız,Fransa\n", encoding="utf-8")
        with DurumDeposu(self.y.durum).degistir() as d:
            d.atama["uzun-roman"] = "gemini-3.8-flash-tts"
        yakinda = site.hazirla(self.y, bildir=lambda s: None)[1]["yakinda"]
        self.assertEqual(yakinda, [
            {"id": "uzun-roman", "no": 2, "eser": "Uzun Roman", "yazar": "Yazar İki", "ulke": "Fransa",
             "koken": "Fransız", "okunuyor": True},
            {"id": "ucuncu", "no": 5, "eser": "Üçüncü", "yazar": "Yazar Beş", "ulke": "", "koken": "",
             "okunuyor": False}])


class OzetOnbellegiTesti(GeciciKokTesti):
    def test_ozet_dosya_degismedikce_yeniden_okunmaz_degisince_degisir(self):
        mp3, kayit = self.kok / "a.mp3", self.kok / "ozetler.json"
        mp3.write_bytes(b"ilk")
        o = site.OzetOnbellegi(kayit)
        ilk = o.ozet(mp3)
        self.assertRegex(ilk, r"^[0-9a-f]{8}$")
        self.assertEqual(list(json.loads(kayit.read_text()).values()), [ilk])
        with mock.patch("builtins.open", side_effect=AssertionError("yeniden okundu")):
            self.assertEqual(site.OzetOnbellegi(kayit).ozet(mp3), ilk)
        mp3.write_bytes(b"ikinci ve daha uzun")
        self.assertNotEqual(site.OzetOnbellegi(kayit).ozet(mp3), ilk)

    def test_bozuk_kayit_dosyasi_yeniden_hesaplatir(self):
        mp3, kayit = self.kok / "a.mp3", self.kok / "ozetler.json"
        mp3.write_bytes(b"veri")
        kayit.write_text("{bozuk")
        self.assertRegex(site.OzetOnbellegi(kayit).ozet(mp3), r"^[0-9a-f]{8}$")


if __name__ == "__main__":
    unittest.main()
