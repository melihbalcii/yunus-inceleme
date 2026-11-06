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


def _cerceve(surum: int, bi: int, si: int, *, dolgu: int = 0, tek: bool = False, etiket: bytes = b"",
             katman: int = 1) -> bytes:
    """ISO 11172-3 başlığıyla yapay MP3 çerçevesi (Katman III). surum: 3 MPEG-1, 2 MPEG-2, 0 MPEG-2.5."""
    b1 = 0xE0 | (surum << 3) | (katman << 1) | 1
    b2 = (bi << 4) | (si << 2) | (dolgu << 1)
    b3 = (3 << 6) if tek else 0
    hz = site._ORNEK[surum][si]
    uzun = (144 if surum == 3 else 72) * site._BIT[1 if surum == 3 else 2][bi] * 1000 // hz + dolgu
    govde = bytearray(uzun - 4)
    if etiket:
        yan = (17 if tek else 32) if surum == 3 else (9 if tek else 17)
        govde[yan:yan + 4] = etiket
    return bytes([0xFF, b1, b2, b3]) + bytes(govde)


class CerceveBasligiTesti(unittest.TestCase):
    def test_surumler_uzunluk_ornek_ve_hz(self):
        for surum, bi, si, uzun, ornek, hz in ((3, 9, 0, 417, 1152, 44100), (3, 14, 1, 960, 1152, 48000),
                                               (2, 8, 1, 192, 576, 24000), (0, 1, 2, 72, 576, 8000)):
            with self.subTest(surum=surum, bi=bi):
                v = _cerceve(surum, bi, si)
                (c,) = site.cerceveler(v)
                self.assertEqual((c.bas, c.uzunluk, c.ornek, c.hz), (0, uzun, ornek, hz))

    def test_dolgu_bayti_ve_art_arda_cerceveler(self):
        v = _cerceve(3, 9, 0, dolgu=1) + _cerceve(3, 9, 0)
        self.assertEqual([(c.bas, c.uzunluk) for c in site.cerceveler(v)], [(0, 418), (418, 417)])

    def test_xing_ve_info_cercevesi_atlanir_konumu_surume_gore(self):
        for surum, tek in ((3, False), (3, True), (2, False), (2, True)):
            for etiket in (b"Xing", b"Info"):
                with self.subTest(surum=surum, tek=tek, etiket=etiket):
                    bi, si = (9, 0) if surum == 3 else (8, 1)
                    v = _cerceve(surum, bi, si, tek=tek, etiket=etiket) + _cerceve(surum, bi, si, tek=tek)
                    self.assertEqual(len(site.cerceveler(v)), 1, "VBR başlığı ses sayılmaz")
        yanlis_yer = bytearray(_cerceve(3, 9, 0))
        yanlis_yer[4 + 17:4 + 21] = b"Xing"  # çift kanallı MPEG-1'de etiket 32. baytta olur
        self.assertEqual(len(site.cerceveler(bytes(yanlis_yer))), 1)

    def test_gecersiz_basliklar_atlanir(self):
        gecerli = _cerceve(3, 9, 0)
        for bozuk in (_cerceve(3, 9, 0, katman=2), bytes([0xFF, 0xEB]) + gecerli[2:],  # Katman II; ayrılmış sürüm
                      bytes([0xFF, 0xFB, 0x00]) + gecerli[3:], bytes([0xFF, 0xFB, 0xF0]) + gecerli[3:],  # bit 0 / 15
                      bytes([0xFF, 0xFB, 0x9C]) + gecerli[3:], bytes([0xFE]) + gecerli[1:]):  # ayrılmış hz; senkron yok
            with self.subTest(bozuk=bozuk[:3].hex()):
                self.assertEqual(site.cerceveler(bozuk), [], "bozuk başlık çerçeve sayılmaz")
                self.assertIn(len(bozuk), [c.bas for c in site.cerceveler(bozuk + gecerli)], "arkasındaki bulunur")

    def test_id3_boyunun_butun_basamaklari_okunur(self):
        gecerli = _cerceve(3, 9, 0)
        for basamaklar, boy in (((0, 1, 0, 0), 16384), ((0, 1, 1, 1), 16384 + 128 + 1), ((0, 0, 0, 0), 0)):
            with self.subTest(boy=boy):
                id3 = b"ID3\x04\x00\x00" + bytes(basamaklar) + b"\xff" * boy
                self.assertEqual([c.bas for c in site.cerceveler(id3 + gecerli)], [10 + boy])
        yarim = b"ID3\x04\x00\x00\x00\x00\x00"  # dosya sonunda 10 bayttan kısa etiket: çökmeden biter
        self.assertEqual([c.bas for c in site.cerceveler(gecerli + yarim)], [0])

    def test_id3_etiketleri_atlanir(self):
        gecerli = _cerceve(3, 9, 0)
        id3v2 = b"ID3\x04\x00\x00" + bytes([0, 0, 1, 0]) + b"\xff" * 128  # eşzamanlı boy: 128
        altbilgili = b"ID3\x04\x00\x10" + bytes([0, 0, 0, 5]) + b"\xff" * 5 + b"3DI" + b"\x00" * 7
        id3v1 = b"TAG" + b"\xff" * 125
        for on in (id3v2, altbilgili):
            self.assertEqual([c.bas for c in site.cerceveler(on + gecerli)], [len(on)])
        self.assertEqual([c.bas for c in site.cerceveler(gecerli + id3v1 + gecerli)], [0, len(gecerli) + 128])


class GomuluEtiketTesti(unittest.TestCase):
    """Etiketin içindeki veri (ör. kapak resmi) MP3 başlığına benzeyen bayt taşıyabilir: etiket atlanmazsa ses sanılır."""

    def test_id3v2_ve_id3v1_icindeki_sahte_cerceve_ses_sayilmaz(self):
        gecerli = _cerceve(3, 9, 0)
        govde = _cerceve(2, 8, 1)  # 192 bayt, geçerli başlıklı
        id3v2 = b"ID3\x04\x00\x00" + bytes([0, 0, 1, 64]) + govde  # boy 192
        self.assertEqual([c.bas for c in site.cerceveler(id3v2 + gecerli)], [len(id3v2)])
        id3v1 = b"TAG" + govde[:125]
        self.assertEqual([c.bas for c in site.cerceveler(gecerli + id3v1 + gecerli)], [0, len(gecerli) + 128])
        self.assertEqual(len(site.cerceveler(b"id3" + bytes([4, 0, 0, 0, 0, 1, 64]) + govde)), 1, "küçük harf etiket değil")

    def test_tam_sinirdaki_cerceve_boluneblir_hata_iletileri(self):
        c = _cerceve(3, 9, 0)
        self.assertEqual(len(site.bol(c, self._k("a"), sinir=len(c))), 1)
        with self.assertRaisesRegex(site.SiteHatasi, "^tek çerçeve parça sınırından büyük$"):
            site.bol(c, self._k("b"), sinir=len(c) - 1)
        with self.assertRaisesRegex(site.SiteHatasi, "^MP3 çerçevesi bulunamadı$"):
            site.bol(b"\x00" * 50, self._k("c"))

    def _k(self, ad):
        import tempfile
        from pathlib import Path
        return Path(tempfile.mkdtemp()) / ad


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


class KodlamaTesti(GeciciKokTesti):
    """Yayın için yeniden kodlama ve bölme (yayında ayrı süreçte çalışır; burada doğrudan sınanır)."""

    def test_kodla_suresi_korunur_64kbps_tek_kanal(self):
        mp3 = self.kok / "kaynak.mp3"
        S.mp3_yaz(mp3, ses(3.0))
        veri, saniye = site.kodla(mp3)
        self.assertAlmostEqual(saniye, 3.0, delta=0.06)
        cer = site.cerceveler(veri)
        self.assertGreater(len(cer), 10)
        self.assertEqual({c.hz for c in cer}, {S.SR})
        b2, b3 = veri[cer[1].bas + 2], veri[cer[1].bas + 3]
        self.assertEqual(site._BIT[2][b2 >> 4], site.KBPS, "64 kbps")
        self.assertEqual(b3 >> 6, 3, "tek kanal")

    def test_parcala_bilgi_dosyasini_en_son_yazar(self):
        mp3 = self.kok / "01 - Eser - Yazar.mp3"
        S.mp3_yaz(mp3, ses(4.0))
        satir = site.parcala(mp3, self.kok / "p")
        bilgi = json.loads((self.kok / "p" / "bilgi.json").read_text())
        self.assertEqual(satir, f"{site.KBPS} kbps, bölündü: {mp3.name} → {len(bilgi['sureler'])} parça")
        self.assertEqual(bilgi["boyut"], sum(p.stat().st_size for p in (self.kok / "p").glob("*.mp3")))
        self.assertAlmostEqual(sum(bilgi["sureler"]), 4.0, delta=site.SURE_TOLERANSI)

    def test_sure_tutmazsa_klasor_silinir_yayin_durur(self):
        mp3 = self.kok / "a.mp3"
        S.mp3_yaz(mp3, ses(2.0))
        with mock.patch.object(site, "bol", lambda veri, k: (k.mkdir(), [0.4])[1]), \
             self.assertRaisesRegex(site.SiteHatasi, r"parçaların süresi tutmuyor: a\.mp3 0\.4 != 2\.[01]$"):
            site.parcala(mp3, self.kok / "p")
        self.assertFalse((self.kok / "p").exists(), "yarım klasör kalmaz")


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


class YayinKapilariTesti(YayinTabani):
    """Yayının kapıları: özet satırları, 10 MB sınırı, listede olmayan ya da vazgeçilen eser."""

    def test_ozet_satirlari(self):
        self.kur()
        mesajlar: list[str] = []
        katalog, _ = site.hazirla(self.y, bildir=mesajlar.append)
        k = katalog[0]
        self.assertIn("1 eser Yakında rafında", mesajlar)
        self.assertEqual(mesajlar[-1], f"1 eser, {len(k['parcalar'])} parça, {round(k['sure'] / 3600, 1)} saat, "
                                       f"{k['boyut'] / 1e9:.2f} GB → {self.y.yayin}")
        self.assertTrue(any(m.startswith(f"{site.KBPS} kbps, bölündü: 01 - Kısa Öykü") for m in mesajlar))

    def test_10_mb_asan_parca_yayini_durdurur(self):
        self.kur()
        site.hazirla(self.y, bildir=lambda s: None)
        parca = next((self.y.yayin / "ses").rglob("1.mp3"))
        parca.write_bytes(b"x" * (site.NETLIFY_SINIRI + 1))
        with self.assertRaisesRegex(site.SiteHatasi, "10 MB'ı aşan parça var"):
            site.hazirla(self.y, bildir=lambda s: None)
        parca.write_bytes(b"x" * site.NETLIFY_SINIRI)
        site.hazirla(self.y, bildir=lambda s: None)  # tam sınır geçer

    def test_vazgecilen_eser_yayina_alinmaz_listede_olmayan_hata(self):
        from sesli.katalog import KatalogHatasi
        self.kur()
        k = self.y.teslim / "Gemini 3.8 Flash"
        S.mp3_yaz(k / "04 - Bırakılan - Yazar Dört.mp3", ses(0.5))
        mesajlar: list[str] = []
        katalog, _ = site.hazirla(self.y, bildir=mesajlar.append, kuru=True)
        self.assertIn("siteye alınmadı (vazgecildi): 04 - Bırakılan - Yazar Dört.mp3", mesajlar)
        S.mp3_yaz(k / "99 - Bilinmeyen - Kimse.mp3", ses(0.5))
        with self.assertRaisesRegex(KatalogHatasi, "eser listesinde karşılığı yok: 99 - Bilinmeyen - Kimse.mp3"):
            site.hazirla(self.y, bildir=lambda s: None, kuru=True)


class SiteDosyalariTesti(YayinTabani):
    def test_alt_klasorler_kopyalanir_ds_store_alinmaz_eskiler_temizlenir(self):
        self.kur()
        pub = self.y.kitaplik / "public"
        (pub / "js").mkdir()
        (pub / "js" / "1-temel.js").write_text("// program")
        (pub / ".DS_Store").write_bytes(b"x")
        site.hazirla(self.y, bildir=lambda s: None)
        self.assertEqual((self.y.yayin / "js" / "1-temel.js").read_text(), "// program")
        self.assertFalse((self.y.yayin / ".DS_Store").exists())
        (self.y.yayin / "eski-klasor").mkdir()
        (self.y.yayin / "eski.txt").write_text("x")
        (pub / "js" / "1-temel.js").write_text("// yeni")
        site.hazirla(self.y, bildir=lambda s: None)
        self.assertEqual((self.y.yayin / "js" / "1-temel.js").read_text(), "// yeni")
        self.assertFalse((self.y.yayin / "eski-klasor").exists())
        self.assertFalse((self.y.yayin / "eski.txt").exists())
        self.assertTrue(any((self.y.yayin / "ses").iterdir()), "ses parçaları yerinde kalır")


class PlansizEserTesti(YayinTabani):
    def test_planda_satiri_olmayan_eserin_koken_ve_ulkesi_bos(self):
        self.kur()
        self.y.plan_csv.write_text("No,Köken,Ülke\n7,Rus,Rusya\n", encoding="utf-8")
        (k,) = site.hazirla(self.y, bildir=lambda s: None)[0]
        self.assertEqual((k["koken"], k["ulke"]), ("", ""))


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
