from __future__ import annotations

import argparse
import contextlib
import io
import json
import unittest

from testler.yardim import GeciciKokTesti, SahteTTS
from sesli import cli
from sesli import gemini as G
from sesli.isci import Cikis, IsTanimi, oku_eser


def _is(**k) -> IsTanimi:
    v = dict(ad="kisa-oyku", arac_adi="Gemini 3.8 Flash TTS", model="m", ses="Fola", ortak=("m2",),
             hedef_sn=600, sabit_blok=None) | k
    return IsTanimi(**v)


class CikisTesti(unittest.TestCase):
    def test_bilinmeyen_kod_hata(self):
        self.assertIs(Cikis.koddan(75), Cikis.KOTA)
        self.assertIs(Cikis.koddan(-9), Cikis.HATA)  # öldürülen süreç

    def test_is_tanimi_komut_satirindan_aynen_doner(self):
        for is_ in (_is(), _is(ortak=(), hedef_sn=None, sabit_blok=2000)):
            a = cli.ayristirici().parse_args(is_.arguman())
            geri = IsTanimi(ad=a.ad, arac_adi=a.arac_adi, model=a.model, ses=a.ses,
                            ortak=tuple(m for m in (a.ortak or "").split(",") if m),
                            hedef_sn=a.hedef_sn, sabit_blok=a.sabit_blok)
            self.assertEqual(geri, is_)


class IsciTesti(GeciciKokTesti):
    def calistir(self, hata: BaseException) -> Cikis:
        self.metin_yaz("kisa-oyku", ["Tek paragraf."])
        with contextlib.redirect_stdout(io.StringIO()):
            return oku_eser(_is(), self.y, tts_kur=lambda arac, y, bildir: SahteTTS([hata]))

    def test_hatalar_cikis_koduna_cevrilir(self):
        self.assertIs(self.calistir(G.KotaDoldu("x")), Cikis.KOTA)
        self.assertIs(self.calistir(G.GuvenlikReddi(10)), Cikis.GUVENLIK)
        self.assertIs(self.calistir(G.GeciciHata("x")), Cikis.GECICI)
        self.assertIs(self.calistir(G.BosYanit("x")), Cikis.BOLUNEMEZ)
        self.assertIs(self.calistir(ValueError("beklenmeyen")), Cikis.HATA)


class BasariliOkumaTesti(GeciciKokTesti):
    """Alt sürecin başarılı yolu: doğru araç ve ayarla okur, MP3'ü ve teslimin dayandığı motor.json'u yazar, kontrol
    sonucunu günlüğe yazar. Ağır ölçümler (Whisper, ses kalitesi modeli) sahte, gerisi gerçek."""

    def calistir(self, kontrol):
        from unittest import mock
        from sesli import isci
        from sesli.kontrol import BlokRaporu, KontrolSonucu
        self.metin_yaz("kisa-oyku", ["Bir paragraf.", "İkinci paragraf."])
        self.araclar, self.ayarlar = [], []
        gercek = isci.Okuyucu

        def okuyucu(tts, ayar, yollar, **k):
            self.ayarlar.append(ayar)
            return gercek(tts, ayar, yollar, olc=lambda m, s: (1.0, []), kalite=lambda s: (3.6, 3.5),
                          yamala=lambda *a, **kw: None, **k)

        def tts_kur(arac, y, bildir):
            self.araclar.append(arac)
            return SahteTTS()
        sonuc = KontrolSonucu(kontrol[0], [BlokRaporu(1, kontrol[1], 1.0, "m", "d", kontrol[2])])
        cikti = io.StringIO()
        with mock.patch.object(isci, "Okuyucu", okuyucu), \
             mock.patch.object(isci, "kontrol_et", lambda f, p, bildir: sonuc), contextlib.redirect_stdout(cikti):
            kod = oku_eser(_is(), self.y, tts_kur=tts_kur)
        return kod, cikti.getvalue()

    def test_okur_motor_kaydini_yazar_kontrolu_bildirir(self):
        kod, cikti = self.calistir((98.5, 0.99, []))
        self.assertIs(kod, Cikis.TAMAM)
        (arac,) = self.araclar
        self.assertEqual((arac.ad, arac.model, arac.ses, arac.sabit_blok), ("Gemini 3.8 Flash TTS", "m", "Fola", None))
        (ayar,) = self.ayarlar
        self.assertEqual((ayar.model, ayar.ses, ayar.ortak, ayar.hedef_sn, ayar.sabit_blok, ayar.siir),
                         ("m", "Fola", ("m2",), 600, None, False))
        fola = self.y.fola_klasoru("kisa-oyku")
        self.assertTrue((fola / "kisa-oyku.mp3").exists())
        self.assertEqual(json.loads((fola / "motor.json").read_text()),
                         {"motor": "Gemini 3.8 Flash TTS", "model": "m", "ses": "Fola"})
        self.assertIn("kontrol: eşleşme %98.50, 0,90 altı 0, atlama 0\n", cikti)

    def test_siir_ve_sabit_blok_ayarlari_okumaya_gecer_motor_kaydi_utf8(self):
        from testler.yardim import ORNEK_ESERLER
        self.eser_listesi_yaz([{**ORNEK_ESERLER[0], "siir": True}, *ORNEK_ESERLER[1:]])
        from unittest import mock
        from sesli import isci
        from sesli.kontrol import KontrolSonucu
        self.metin_yaz("kisa-oyku", ["Bir dize\nikinci dize."])
        ayarlar, araclar = [], []
        gercek = isci.Okuyucu

        def okuyucu(tts, ayar, yollar, **k):
            ayarlar.append(ayar)
            return gercek(tts, ayar, yollar, olc=lambda m, s: (1.0, []), kalite=lambda s: (3.6, 3.5),
                          yamala=lambda *a, **kw: None, **k)
        with mock.patch.object(isci, "Okuyucu", okuyucu), \
             mock.patch.object(isci, "kontrol_et", lambda f, p, bildir: KontrolSonucu(99.0, [])), \
             contextlib.redirect_stdout(io.StringIO()):
            kod = oku_eser(_is(arac_adi="Gemini 3.1 Flash TTS", ses="Sulafat", hedef_sn=None, sabit_blok=2000,
                               ortak=()), self.y,
                           tts_kur=lambda arac, y, b: (araclar.append(arac), SahteTTS())[1])
        self.assertIs(kod, Cikis.TAMAM)
        self.assertEqual((ayarlar[0].siir, ayarlar[0].sabit_blok, ayarlar[0].hedef_sn), (True, 2000, None))
        self.assertEqual(araclar[0].sabit_blok, 2000)
        motor = (self.y.fola_klasoru("kisa-oyku") / "motor.json").read_text(encoding="utf-8")
        self.assertEqual(json.loads(motor), {"motor": "Gemini 3.1 Flash TTS", "model": "m", "ses": "Sulafat"})

    def test_kontrolden_gecmeyen_okuma_gunlukte_belirtilir(self):
        _, cikti = self.calistir((95.0, 0.85, ["atlanan"]))
        self.assertIn("kontrol: eşleşme %95.00, 0,90 altı 1, atlama 1 — GEÇMEDİ\n", cikti)


class CliTabani(GeciciKokTesti):
    """CLI testlerinin ortak yardımcısı (test içermez)."""

    def calistir(self, *arg: str) -> tuple[int, str]:
        cikti, uyari = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(cikti), contextlib.redirect_stderr(uyari):
            kod = cli.main(list(arg), yollar=self.y)
        return kod, cikti.getvalue() + uyari.getvalue()


class CliTesti(CliTabani):
    def test_durum(self):
        self.metin_yaz("kisa-oyku", ["kısa"])
        self.y.durum.write_text(json.dumps({"atama": {"kisa-oyku": "m1"}, "ortak": {"kisa-oyku": ["m2"]}}))
        kod, cikti = self.calistir("durum")
        self.assertEqual(kod, 0)
        self.assertIn("okunuyor: m1 + m2", cikti)
        self.assertIn("okunmayacak", cikti)  # Emel kopyası olmayan eser
        self.assertIn("Kuyruk (kısadan uzuna): kisa-oyku", cikti)

    def test_hazirla(self):
        self.metin_yaz("kisa-oyku", ["Bir.", "İki."])
        kod, _ = self.calistir("hazirla", "kisa-oyku")
        self.assertEqual(kod, 0)
        self.assertTrue((self.y.fola_klasoru("kisa-oyku") / "seslendirme-metni.txt").exists())

    def test_teslim_kayit_yoksa_bildirir(self):
        kod, cikti = self.calistir("teslim", "kisa-oyku")
        self.assertEqual(kod, 1)
        self.assertIn("okuma kaydı yok", cikti)

    def test_bilinmeyen_komut(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main(["yok"], yollar=self.y)


class AyristiriciTesti(unittest.TestCase):
    def ayir(self, *arg: str):
        return cli.ayristirici().parse_args(list(arg))

    def test_komutlar_dogru_isleve_gider(self):
        for arg, isl in ((["durum"], cli._durum), (["oku"], cli._oku), (["kontrol", "x"], cli._kontrol),
                         (["ceviri", "x"], cli._ceviri), (["hazirla", "x"], cli._hazirla), (["teslim"], cli._teslim),
                         (["site"], cli._site),
                         (["oku-eser", "x", "--arac-adi", "A", "--model", "m", "--ses", "Fola", "--hedef-sn", "9"],
                          cli._oku_eser)):
            self.assertIs(self.ayir(*arg).is_, isl, arg)

    def test_oku_gunluk_haklari_varsayilan_10_tamsayi(self):
        a = self.ayir("oku")
        self.assertEqual((a.lite, a.flash, a.k31), (10, 10, 10))
        a = self.ayir("oku", "--k31", "0", "--lite", "3")
        self.assertEqual((a.lite, a.flash, a.k31), (3, 10, 0))

    def test_oku_eser_zorunlulari_ve_plan_secenegi(self):
        temel = ["oku-eser", "x", "--arac-adi", "A", "--model", "m", "--ses", "Fola"]
        a = self.ayir(*temel, "--sabit-blok", "3400", "--ortak", "m2,m3")
        self.assertEqual((a.ad, a.arac_adi, a.model, a.ses, a.ortak, a.sabit_blok, a.hedef_sn),
                         ("x", "A", "m", "Fola", "m2,m3", 3400, None))
        for eksik in (temel, temel + ["--hedef-sn", "1", "--sabit-blok", "2"], temel[:2] + ["--hedef-sn", "1"]):
            with self.subTest(eksik=eksik), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.ayir(*eksik)

    def test_teslim_adi_istege_bagli_site_kuru_bayragi(self):
        self.assertIsNone(self.ayir("teslim").ad)
        self.assertEqual(self.ayir("teslim", "x").ad, "x")
        self.assertFalse(self.ayir("site").kuru)
        self.assertTrue(self.ayir("site", "--kuru").kuru)

    def test_alt_komut_kullanimi_ve_secenek_yardimi(self):
        ap = cli.ayristirici()
        self.assertEqual(ap.format_usage(), "usage: sesli_kitap.py [-h] komut ...\n")
        self.assertIn("Sesli kitap üretim sistemi", ap.format_help())
        alt = next(a for a in ap._actions if isinstance(a, argparse._SubParsersAction)).choices
        yardim = {ad: " ".join(p.format_help().split()) for ad, p in alt.items()}
        for ad in ("3.8 Flash Lite", "3.8 Flash", "3.1 Flash"):
            self.assertIn(f"{ad} günlük istek hakkı (0: kullanma)", yardim["oku"])
        self.assertIn("--kuru hiçbir şey yazmadan sonucu göster", yardim["site"])
        self.assertIn("usage: sesli_kitap.py teslim [-h] [ad]", yardim["teslim"])
        self.assertIn("--arac-adi ARAC_ADI --model MODEL --ses SES [--ortak ORTAK] "
                      "(--hedef-sn HEDEF_SN | --sabit-blok SABIT_BLOK) ad", yardim["oku-eser"])
        for ad in ("kontrol", "ceviri", "hazirla"):
            self.assertIn(f"usage: sesli_kitap.py {ad} [-h] ad", yardim[ad])

    def test_yardim_metni_komutlari_turkce_anlatir(self):
        yardim = cli.ayristirici().format_help()
        for parca in ("eserlerin ve okumanın durumu", "zamanlayıcıyı başlatır", "okunmuş eseri yeniden kontrol eder",
                      "çeviri bölümlerini birleştirir", "okuma metnini günceller",
                      "kontrolden geçen okumaları teslim eder", "site yayın klasörünü hazırlar"):
            self.assertIn(parca, yardim)


class DurumCiktisiTesti(CliTabani):
    def test_durum_her_eserin_durumunu_ve_bugunku_istekleri_yazar(self):
        from sesli.kota import kota_gunu
        import datetime as dt
        self.metin_yaz("kisa-oyku", ["kısa"])
        self.metin_yaz("uzun-roman", ["uzun " * 50])
        self.y.durum.write_text(json.dumps({"atama": {"uzun-roman": "m1"}}))
        teslim = self.y.teslim / "Gemini 3.8 Flash"
        teslim.mkdir()
        (teslim / "01 - Kısa Öykü - Yazar Bir.mp3").write_bytes(b"x")
        fola = self.y.fola_klasoru("uzun-roman")
        fola.mkdir(parents=True, exist_ok=True)
        (fola / "kontrol.json").write_text(json.dumps({"eslesme": 96.5, "bloklar": []}))
        zaman = dt.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
        self.y.istek_defteri.write_text("".join(json.dumps({"zaman": zaman, "sonuc": s}) + "\n"
                                                for s in ("ses", "ses", "ses", "kayip", "gitmedi")))
        kod, cikti = self.calistir("durum")
        self.assertEqual(kod, 0)
        satir = {x.split()[0]: x for x in cikti.splitlines() if x[:3].strip().isdigit()}
        self.assertIn("teslim edildi (Gemini 3.8 Flash)", satir["1"])
        self.assertIn("okunuyor: m1; kontrol %96.50 GEÇMEDİ", satir["2"])
        self.assertIn("okunmayacak (Emel'li kopyası yok, yalniz_fola değil)", satir["3"])
        self.assertNotIn("4", satir, "vazgeçilen eser listelenmez")
        self.assertIn("Kuyruk (kısadan uzuna): uzun-roman (", cikti)
        self.assertIn(f"Bugünkü istekler (kota günü {kota_gunu()}): 4 kota harcayan istek, 3 ses geldi, 1 boşa gitti "
                      "(%25); ayrıntı: gitmedi 1, kayip 1, ses 3", cikti)

    def test_istek_yoksa_bos_kuyruk_ve_sifir_yazar(self):
        kod, cikti = self.calistir("durum")
        self.assertEqual(kod, 0)
        self.assertIn("0 kota harcayan istek, 0 ses geldi, 0 boşa gitti\n", cikti)


class KomutTesti(CliTabani):
    """Ağır işleri çağıran komutlar: doğru argümanla çağırır, sonucu doğru yazar, doğru çıkış kodunu döner."""

    def test_oku_eser_is_tanimini_kurar_cikis_kodunu_doner(self):
        from unittest import mock
        gelen = []
        with mock.patch.object(cli, "oku_eser", lambda is_, y: (gelen.append((is_, y)), Cikis.KOTA)[1]):
            kod, _ = self.calistir("oku-eser", "kisa-oyku", "--arac-adi", "A", "--model", "m", "--ses", "Fola",
                                   "--ortak", "m2,,m3", "--hedef-sn", "900")
        self.assertEqual(kod, int(Cikis.KOTA))
        ((is_, y),) = gelen
        self.assertIs(y, self.y)
        self.assertEqual(is_, IsTanimi(ad="kisa-oyku", arac_adi="A", model="m", ses="Fola", ortak=("m2", "m3"),
                                       hedef_sn=900, sabit_blok=None))
        with mock.patch.object(cli, "oku_eser", lambda is_, y: (gelen.append((is_, y)), Cikis.TAMAM)[1]):
            self.calistir("oku-eser", "x", "--arac-adi", "A", "--model", "m", "--ses", "S", "--sabit-blok", "2000")
        self.assertEqual((gelen[-1][0].ortak, gelen[-1][0].sabit_blok, gelen[-1][0].hedef_sn), ((), 2000, None))

    def test_kontrol_ozeti_yazar_gecmezse_1(self):
        from unittest import mock
        from sesli.kontrol import BlokRaporu, KontrolSonucu
        for sonuc, kod_b in ((KontrolSonucu(99.0, [BlokRaporu(1, 0.99, 1.0, "m", "d", [])]), 0),
                             (KontrolSonucu(90.0, [BlokRaporu(1, 0.8, 1.0, "m", "d", ["a b c"])]), 1)):
            with mock.patch.object(cli, "kontrol_et", lambda f, p, s=sonuc: s):
                kod, cikti = self.calistir("kontrol", "kisa-oyku")
            self.assertEqual(kod, kod_b)
            self.assertTrue(cikti.startswith("PARAGRAF 1 | harf düzeyinde eşleşme"), cikti)
            self.assertNotIn("[1/1]", cikti, "blok blok satırlar değil, özet")
        with mock.patch.object(cli, "kontrol_et", lambda f, p: KontrolSonucu(0.0, [])):
            self.assertEqual(self.calistir("kontrol", "kisa-oyku"), (1, "blok yok\n"))

    def test_site_kuru_calisma_ozet_yazar(self):
        from unittest import mock
        with mock.patch.object(cli.site, "hazirla", lambda y, kuru: ([{"id": 1}, {"id": 2}],
                                                                    {"yakinda": [{"id": "a"}, {"id": "b"}]})):
            self.assertEqual(self.calistir("site", "--kuru"), (0, "2 eser yayında olurdu; Yakında: a, b\n"))
        with mock.patch.object(cli.site, "hazirla", lambda y, kuru: ([], {"yakinda": []})):
            self.assertEqual(self.calistir("site", "--kuru"), (0, "0 eser yayında olurdu; Yakında: boş\n"))
            self.assertEqual(self.calistir("site"), (0, ""))

    def test_ceviri_paragraf_kelime_ve_okunussuz_adlar(self):
        from unittest import mock
        self.metin_yaz("kisa-oyku", ["Metin."])
        with mock.patch.object(cli.ceviri, "yaz", lambda ad, y: (12, 3456)), \
             mock.patch.object(cli.ceviri, "okunussuz_adlar", lambda m: [f"Ad{i}" for i in range(70)]):
            kod, cikti = self.calistir("ceviri", "kisa-oyku")
        self.assertEqual(kod, 0)
        self.assertIn("paragraf: 12 | kelime: 3,456\n", cikti)
        self.assertIn("okunuşu yazılmamış olabilecek adlar: Ad0, Ad1", cikti)
        self.assertIn("Ad59\n", cikti)
        self.assertNotIn("Ad60", cikti, "en çok 60 ad")
        with mock.patch.object(cli.ceviri, "yaz", lambda ad, y: (1, 1)), \
             mock.patch.object(cli.ceviri, "okunussuz_adlar", lambda m: []):
            self.assertEqual(self.calistir("ceviri", "kisa-oyku"), (0, "paragraf: 1 | kelime: 1\n"))

    def test_oku_zamanlayiciyi_kotalarla_kurar_ikinci_kopyada_1(self):
        from unittest import mock
        from sesli.kilit import tek_kopya
        kurulan = []

        class Z:
            def calis(self):
                kurulan.append("çalıştı")
        with mock.patch.object(cli, "kur", lambda y, k: (kurulan.append(k), Z())[1]):
            self.assertEqual(self.calistir("oku", "--k31", "0"), (0, ""))
            self.assertEqual(kurulan, [{"gemini-3.8-flash-lite-tts": 10, "gemini-3.8-flash-tts": 10,
                                        "gemini-3.1-flash-tts-preview": 0}, "çalıştı"])
            self.y.tmp.mkdir(exist_ok=True)
            with tek_kopya(self.y.zamanlayici_kilidi):
                kod, cikti = self.calistir("oku")
        self.assertEqual(kod, 1)
        self.assertIn("okuma programı zaten çalışıyor; ikinci kopya başlatılmadı", cikti)


class AltSurecTesti(GeciciKokTesti):
    def test_calistir_projenin_pythonu_ile_alt_sureci_baslatir(self):
        from types import SimpleNamespace
        from unittest import mock
        from sesli import isci
        gelen = []
        with mock.patch.object(isci.subprocess, "run", lambda arg, check: (gelen.append((arg, check)),
                                                                            SimpleNamespace(returncode=77))[1]):
            self.assertIs(isci.calistir(_is(), self.y), Cikis.GECICI)
        ((arg, check),) = gelen
        self.assertEqual(arg[:3], [str(self.y.python), "-u", str(self.y.kok / "araclar" / "sesli_kitap.py")])
        self.assertEqual(arg[3:], _is().arguman())
        self.assertFalse(check)

    def test_cikis_kodlari_sabit(self):
        self.assertEqual({c.name: int(c) for c in Cikis},
                         {"TAMAM": 0, "HATA": 1, "KOTA": 75, "GUVENLIK": 76, "GECICI": 77, "BOLUNEMEZ": 78})

    def test_gercek_tts_anahtari_env_den_okur_defteri_dosyaya_yazar(self):
        import json
        from sesli import isci
        from sesli.ayar import AyarHatasi
        arac = G.Arac("Deneme TTS", "m", "Fola")
        with self.assertRaises(AyarHatasi):
            isci._gercek_tts(arac, self.y, lambda s: None)
        self.y.gemini_env.write_text("GEMINI_API_KEY=deneme-anahtari\n")
        t = isci._gercek_tts(arac, self.y, lambda s: None)
        self.assertIsInstance(t, G.GeminiTTS)
        self.assertEqual((t.arac, t._anahtar), (arac, "deneme-anahtari"))
        t._defter({"sonuc": "ses"})
        self.assertEqual(json.loads(self.y.istek_defteri.read_text()), {"sonuc": "ses"})


class OkunussuzAdTesti(unittest.TestCase):
    def test_ingilizce_gorunen_buyuk_harfli_sozcukler(self):
        from sesli.ceviri import okunussuz_adlar
        metin = "Martin İdın ile Ruth, Wiki, Smith-son, Brooks ve Cek konuştu. Ash geldi, Ash gitti. Bugh. Lee."
        self.assertEqual(okunussuz_adlar(metin), ["Ash", "Brooks", "Bugh", "Lee", "Ruth", "Smith-son", "Wiki"])
        self.assertEqual(okunussuz_adlar("Ali Veli Ayşe Mehmet."), [])


class DurumSatirTesti(CliTabani):
    def test_satirlarin_tam_bicimi(self):
        self.metin_yaz("kisa-oyku", ["kısa"])
        self.metin_yaz("uzun-roman", ["uzun"])
        self.y.durum.write_text(json.dumps({"atama": {"kisa-oyku": "m1"}, "ortak": {"kisa-oyku": ["m2", "m3"]}}))
        teslim = self.y.teslim / "Gemini 3.8 Flash"
        teslim.mkdir()
        (teslim / "02 - Uzun Roman - Yazar İki.mp3").write_bytes(b"x")
        fola = self.y.fola_klasoru("uzun-roman")
        fola.mkdir(parents=True, exist_ok=True)
        (fola / "kontrol.json").write_text(json.dumps({"eslesme": 99.1, "bloklar": []}))
        fola = self.y.fola_klasoru("kisa-oyku")
        fola.mkdir(parents=True, exist_ok=True)
        (fola / "kontrol.json").write_text(json.dumps({"eslesme": 99.1, "bloklar": []}))
        _, cikti = self.calistir("durum")
        satirlar = cikti.splitlines()
        self.assertEqual(satirlar[0], " No  Eser                                       Durum")
        self.assertIn(f"  1  {'Kısa Öykü':<42} okunuyor: m1 + m2, m3; kontrol %99.10 geçti", satirlar)
        self.assertIn(f"  2  {'Uzun Roman':<42} teslim edildi (Gemini 3.8 Flash)", satirlar, "teslimde kontrol yazılmaz")
        self.assertIn("Kuyruk (kısadan uzuna): kisa-oyku (5 kr)", cikti)


if __name__ == "__main__":
    unittest.main()
