"""Okuyucu: sahte TTS, sahte Whisper ölçümü ve sahte kalite ölçümüyle (ağ ve model yok)."""
from __future__ import annotations

import itertools
import json
import unittest

from testler.yardim import GeciciKokTesti, SahteTTS, ses
from sesli import gemini as G
from sesli import okuma as O
from sesli.ses import SR


def iyi_olcum(metin, ses_):
    return 1.0, []


def iyi_kalite(ses_):
    return 3.6, 3.5


class OkuyucuTabani(GeciciKokTesti):
    """Okuyucu testlerinin ortak yardımcıları (test içermez: alt sınıflar testleri tekrarlamasın)."""

    def okuyucu(self, tts, *, olc=iyi_olcum, kalite=iyi_kalite, yamala=None, **ayar):
        a = O.OkumaAyari(model="m1", ses="Fola", **({"hedef_sn": 60} | ayar))
        self.mesajlar: list[str] = []
        return O.Okuyucu(tts, a, self.y, bildir=self.mesajlar.append, olc=olc, kalite=kalite,
                         yamala=yamala or (lambda *a, **k: None))

    def eser(self, paragraf_sayisi=12, boy=300):
        d = self.metin_yaz("kisa-oyku", [f"Paragraf {i}. " + "k" * boy for i in range(paragraf_sayisi)])
        return d, self.y.fola_klasoru("kisa-oyku") / "kisa-oyku.mp3"


class OkuyucuTesti(OkuyucuTabani):
    def test_eser_okunur_ve_kayitlar_yazilir(self):
        metin, cikti = self.eser()
        cikti.parent.mkdir(parents=True)
        tts = SahteTTS()
        self.okuyucu(tts).eseri_oku(metin, cikti)
        self.assertTrue(cikti.exists())
        plan = json.loads((cikti.parent / "plan.json").read_text())
        kalite = json.loads((cikti.parent / "kalite.json").read_text())
        self.assertEqual(len(plan), len(tts.istekler))
        self.assertEqual([k["bozuk"] for k in kalite], [False] * len(plan))
        self.assertEqual("".join(p["metin"] for p in plan).count("Paragraf"), 12)
        self.assertTrue((cikti.parent / "blok-plan.json").exists())

    def test_ikinci_okumada_istek_atilmaz(self):
        metin, cikti = self.eser()
        cikti.parent.mkdir(parents=True)
        self.okuyucu(SahteTTS()).eseri_oku(metin, cikti)
        tts = SahteTTS()
        self.okuyucu(tts).eseri_oku(metin, cikti)
        self.assertEqual(tts.istekler, [])

    def test_kota_dolunca_okunan_bloklar_kalir(self):
        metin, cikti = self.eser()
        cikti.parent.mkdir(parents=True)
        tts = SahteTTS([None, G.KotaDoldu("bitti")])
        with self.assertRaises(G.KotaDoldu):
            self.okuyucu(tts).eseri_oku(metin, cikti)
        self.assertEqual(len(list(self.y.parcalar.glob("*.wav"))), 1)
        tts2 = SahteTTS()
        self.okuyucu(tts2).eseri_oku(metin, cikti)  # ertesi gün: ilk blok önbellekten
        self.assertNotIn(tts.istekler[0], tts2.istekler)

    def test_ortak_aracin_bloklari_ve_plani_gecerli(self):
        metin, cikti = self.eser()
        cikti.parent.mkdir(parents=True)
        self.okuyucu(SahteTTS()).eseri_oku(metin, cikti)
        tts = SahteTTS()
        o = O.Okuyucu(tts, O.OkumaAyari(model="m2", ses="Fola", ortak=("m1",), hedef_sn=60), self.y,
                      bildir=lambda s: None, olc=iyi_olcum, kalite=iyi_kalite, yamala=lambda *a, **k: None)
        o.eseri_oku(metin, cikti)
        self.assertEqual(tts.istekler, [])

    def test_bos_yanitta_blok_ikiye_bolunur(self):
        tts = SahteTTS([G.BosYanit("x")])
        sonuc = self.okuyucu(tts).seslendir("Bir.\n\nİki.\n\nÜç.", "[1]")
        # bölme noktası: biriken uzunluk yarıyı ilk geçtiği paragraf (eski seslendir_gemini ile aynı)
        self.assertEqual(tts.istekler[1:], ["Bir.", "İki.\n\nÜç."])
        self.assertGreater(len(sonuc), 0)

    def test_tek_paragraf_bolunemez(self):
        with self.assertRaises(O.BolunemezHata):
            self.okuyucu(SahteTTS([G.BosYanit("x")])).seslendir("Tek paragraf.", "[1]")

    def test_uzun_guvenlik_reddi_bolunur_kisasi_yukari_iletilir(self):
        uzun = G.GuvenlikReddi(5000)
        tts = SahteTTS([uzun])
        self.okuyucu(tts).seslendir("Bir.\n\nİki.", "[1]")
        self.assertEqual(len(tts.istekler), 3)
        with self.assertRaises(G.GuvenlikReddi):
            self.okuyucu(SahteTTS([G.GuvenlikReddi(10)])).seslendir("Bir.", "[1]")

    def test_kotu_okuma_yinelenir_en_iyisi_tutulur(self):
        oranlar = iter([(0.80, []), (0.90, []), (0.85, [])])
        tts = SahteTTS()
        self.okuyucu(tts, olc=lambda m, s: next(oranlar)).seslendir("Metin.", "[1]")
        self.assertEqual(len(tts.istekler), O.DENEME)
        olcumler = [json.loads(x) for x in self.y.olcum.read_text().splitlines()]
        self.assertEqual([o["oran"] for o in olcumler], [0.8, 0.9, 0.85])

    def test_yama_basarili_olursa_yeniden_okunmaz(self):
        oranlar = iter([(0.93, ["eksik kelimeler burada"]), (0.99, [])])
        yamali = ses(1.0, 0.1)
        tts = SahteTTS()
        sonuc = self.okuyucu(tts, olc=lambda m, s: next(oranlar),
                             yamala=lambda *a, **k: yamali).seslendir("Metin.", "[1]")
        self.assertIs(sonuc, yamali)
        self.assertEqual(len(tts.istekler), 1)

    def test_bozulan_ses_yamalanmaz(self):
        cagrildi = []
        tts = SahteTTS()
        self.okuyucu(tts, kalite=lambda s: (3.8, 1.5),
                     yamala=lambda *a, **k: cagrildi.append(1)).seslendir("Metin.", "[1]")
        self.assertEqual(cagrildi, [])
        self.assertEqual(len(tts.istekler), O.DENEME)

    def test_sabit_plan(self):
        metin, cikti = self.eser(paragraf_sayisi=10, boy=900)
        cikti.parent.mkdir(parents=True)
        tts = SahteTTS()
        a = O.OkumaAyari(model="m3", ses="Sulafat", sabit_blok=2000)
        O.Okuyucu(tts, a, self.y, bildir=lambda s: None, olc=iyi_olcum, kalite=iyi_kalite).eseri_oku(metin, cikti)
        self.assertTrue(all(len(x) <= 2200 for x in tts.istekler))
        self.assertFalse((cikti.parent / "blok-plan.json").exists())

    def test_blok_dosya_adi_sabit(self):
        """Önbellek adı değişirse okunmuş bütün bloklar kaybolur: biçim sabit kalmalı."""
        self.assertEqual(O.blok_ozeti("Merhaba.", "gemini-3.8-flash-tts", "Fola"),
                         __import__("hashlib").md5(f"Merhaba.|gemini-3.8-flash-tts|Fola|{G.USLUP}".encode())
                         .hexdigest()[:12])

    def test_ses_suresi_bloklarin_toplami(self):
        metin, cikti = self.eser(paragraf_sayisi=3, boy=150)
        cikti.parent.mkdir(parents=True)
        tts = SahteTTS(kr_sn=15.0)
        sure = self.okuyucu(tts).eseri_oku(metin, cikti)
        beklenen = sum(max(0.5, len(m) / 15.0) + O.BLOK_ARASI for m in tts.istekler) / 60
        self.assertAlmostEqual(sure, beklenen, delta=1 / SR)



class OkumaKayitlariTesti(OkuyucuTabani):
    """Okumanın yan çıktıları: ölçüm kaydı (okuma hızı ve başarı oranı buradan hesaplanır), günlük satırları (kayıt
    denetimi bunları okur) ve blok planı (ortak araç onu sürdürür; yanlış kullanılırsa bloklar baştan okunur)."""

    def test_olcum_kaydi_her_blok_icin_dogru_alanlarla_yazilir(self):
        metin, cikti = self.eser()
        cikti.parent.mkdir(parents=True)
        olculen: list[str] = []

        def olc(m, s):
            olculen.append(m)
            return 0.987654, []
        self.okuyucu(SahteTTS(), olc=olc, kalite=lambda s: (3.6123, 3.4987)).eseri_oku(metin, cikti)
        plan = json.loads((cikti.parent / "plan.json").read_text())
        kayitlar = [json.loads(x) for x in self.y.olcum.read_text().splitlines()]
        self.assertEqual(olculen, [p["metin"] for p in plan], "her blok kendi metniyle ölçülmeli")
        self.assertEqual(len(kayitlar), len(plan))
        for k, p in zip(kayitlar, plan, strict=True):
            sn = round(len(O.S.wav_oku(self.y.parcalar / p["dosya"])) / SR, 1)
            self.assertEqual({x: v for x, v in k.items() if x != "zaman"},
                             {"model": "m1", "kr": len(p["metin"]), "sn": sn, "oran": 0.9877, "iyi": True,
                              "atlama": 0, "kalite": [3.61, 3.5]})

    def test_gunluk_satirlari_kayit_denetiminin_aradigi_sozcukleri_tasir(self):
        import haftalik_denetim as H
        metin, cikti = self.eser(paragraf_sayisi=2)
        cikti.parent.mkdir(parents=True)
        sonuclar = itertools.chain([(0.90, ["atlanan söz"])], itertools.repeat((0.99, [])))
        kaliteler = itertools.chain([(3.5, 2.0)], itertools.repeat((3.6, 3.5)))
        self.okuyucu(SahteTTS(), olc=lambda m, s: next(sonuclar), kalite=lambda s: next(kaliteler)
                     ).eseri_oku(metin, cikti)
        ilk = next(m for m in self.mesajlar if "eşleşme 0.900" in m)
        self.assertIn("ATLAMA: ['atlanan söz']", ilk)
        self.assertIn("SES BOZULUYOR", ilk)
        self.assertIn("(deneme 1/3)", ilk)
        self.assertTrue(all(t in ilk for t in H.YARIM_DENEME), "kayıt denetimi yarım denemeyi tanımalı")
        ikinci = next(m for m in self.mesajlar if "eşleşme 0.990" in m)
        self.assertFalse(any(t in ikinci for t in H.YARIM_DENEME), "iyi okuma yarım deneme sayılmamalı")

    def test_blok_planinin_kimligi_eseri_ve_araci_tanimlar(self):
        metin, cikti = self.eser()
        cikti.parent.mkdir(parents=True)
        self.okuyucu(SahteTTS()).eseri_oku(metin, cikti)
        kimlik = json.loads((cikti.parent / "blok-plan.json").read_text())["kimlik"]
        self.assertEqual(kimlik, {"model": "m1", "ses": "Fola", "uslup": O.USLUP, "paragraf": 12,
                                  "karakter": sum(len(f"Paragraf {i}. " + "k" * 300) for i in range(12))})

    def _ikinci_arac(self, **ayar):
        return O.Okuyucu(SahteTTS(), O.OkumaAyari(**({"model": "m2", "ses": "Fola", "hedef_sn": 60} | ayar)), self.y,
                         bildir=lambda s: None, olc=iyi_olcum, kalite=iyi_kalite, yamala=lambda *a, **k: None)

    def test_ortak_arac_planin_kimligini_degistirmez(self):
        metin, cikti = self.eser()
        cikti.parent.mkdir(parents=True)
        self.okuyucu(SahteTTS()).eseri_oku(metin, cikti)
        self._ikinci_arac(ortak=("m1",)).eseri_oku(metin, cikti)
        self.assertEqual(json.loads((cikti.parent / "blok-plan.json").read_text())["kimlik"]["model"], "m1")

    def test_ortak_olmayan_ya_da_sesi_farkli_arac_plani_yeniden_kurar(self):
        for ayar in ({}, {"ortak": ("m1",), "ses": "Sulafat"}):
            with self.subTest(ayar=ayar):
                self.setUp()
                metin, cikti = self.eser()
                cikti.parent.mkdir(parents=True)
                self.okuyucu(SahteTTS()).eseri_oku(metin, cikti)
                o = self._ikinci_arac(**ayar)
                o.eseri_oku(metin, cikti)
                kimlik = json.loads((cikti.parent / "blok-plan.json").read_text())["kimlik"]
                self.assertEqual((kimlik["model"], kimlik["ses"]), ("m2", ayar.get("ses", "Fola")))
                self.assertGreater(len(o.tts.istekler), 0, "başka araç/ses önbellekteki blokları kullanamaz")


class BekleyenOkumaTesti(OkuyucuTabani):
    """H-018: diske yazılıp ölçülmeden kalmış okuma, açılışta istek atılmadan ölçülür (aynı süreçte)."""

    def test_bekleyen_okuma_istek_atmadan_olculur(self):
        metin = "Bir iki üç dört beş."
        o = self.okuyucu(SahteTTS())
        depo = o._depo(metin)
        depo.sakla(ses(1.5))
        olculen = []
        tts = SahteTTS()
        sonuc = self.okuyucu(tts, olc=lambda m, s_: (olculen.append((m, len(s_))), (0.99, []))[1]).seslendir(metin, "[4]")
        self.assertEqual(tts.istekler, [])
        self.assertEqual(olculen, [(metin, int(1.5 * SR))])
        self.assertEqual(len(sonuc), int(1.5 * SR))
        self.assertIn(f"[4] ölçülmeden kalmış okuma ölçülüyor (yeni istek yok): {depo.bekleyen[0]}", self.mesajlar)
        yeni = o._depo(metin)
        self.assertEqual((yeni.bekleyen, [d.dosya for d in yeni.denemeler]), ([], [depo.bekleyen[0]]))

    def test_bozuk_ya_da_dosyasi_olmayan_bekleyen_alinmaz(self):
        metin = "Bir iki üç."
        depo = self.okuyucu(SahteTTS())._depo(metin)
        ad = depo.sakla(ses(0.5))
        (self.y.parcalar / ad).unlink()
        kayit = json.loads(depo._kayit.read_text())
        kayit["bekleyen"] += ["../disari.wav"]
        depo._kayit.write_text(json.dumps(kayit))
        self.assertEqual(self.okuyucu(SahteTTS())._depo(metin).bekleyen, [])


class PlanDogrulamaTesti(OkuyucuTabani):
    def test_gecersiz_sinirlar_yok_sayilir_gecerli_kullanilir(self):
        metin, cikti = self.eser()
        cikti.parent.mkdir(parents=True)
        self.okuyucu(SahteTTS()).eseri_oku(metin, cikti)
        plan_yolu = cikti.parent / "blok-plan.json"
        kayit = json.loads(plan_yolu.read_text())
        o = self.okuyucu(SahteTTS())
        self.assertEqual(o._plan_oku(plan_yolu, 12), (kayit["kimlik"], kayit["sinirlar"]))
        for sinirlar in ([3, 2], [3, 3], [0, 5], [5, 13], [2.0, 5], "3,6", [True]):
            with self.subTest(sinirlar=sinirlar):
                plan_yolu.write_text(json.dumps({"kimlik": kayit["kimlik"], "sinirlar": sinirlar}))
                self.mesajlar.clear()
                self.assertEqual(o._plan_oku(plan_yolu, 12), ({}, []))
                self.assertTrue(self.mesajlar[0].startswith("UYARI:"))
        plan_yolu.write_text(json.dumps({"kimlik": {"a": [1]}, "sinirlar": [3]}))
        self.assertEqual(o._plan_oku(plan_yolu, 12), ({}, []))
        plan_yolu.write_text(json.dumps({"kimlik": kayit["kimlik"]}))
        self.assertEqual(o._plan_oku(plan_yolu, 12), (kayit["kimlik"], []), "sınırsız plan: yeniden hesaplanır")


class EserKayitlariTesti(OkuyucuTabani):
    def test_plan_kalite_ve_bitis_kayitlari_eksiksiz(self):
        metin, cikti = self.eser(paragraf_sayisi=6, boy=300)
        cikti.parent.mkdir(parents=True)
        sure = self.okuyucu(SahteTTS(), kalite=lambda s: (3.567, 3.512)).eseri_oku(metin, cikti)
        plan = json.loads((cikti.parent / "plan.json").read_text())
        kalite = json.loads((cikti.parent / "kalite.json").read_text())
        self.assertGreater(len(plan), 1)
        self.assertEqual([p["no"] for p in plan], list(range(1, len(plan) + 1)))
        self.assertEqual({p["tarz"] for p in plan}, {"blok"})
        self.assertTrue(all((self.y.parcalar / p["dosya"]).exists() for p in plan))
        self.assertEqual("\n\n".join(p["metin"] for p in plan).count("Paragraf"), 6)
        self.assertEqual(kalite, [{"no": n, "bas": 3.57, "son": 3.51, "bozuk": False} for n in range(1, len(plan) + 1)])
        self.assertEqual(self.mesajlar[-1], f"BITTI {cikti} süre {sure:.1f} dk")
        toplam = sum(len(O.S.wav_oku(self.y.parcalar / p["dosya"])) for p in plan) / SR + len(plan) * O.BLOK_ARASI
        self.assertAlmostEqual(sure, toplam / 60, places=3)
        self.assertTrue(cikti.exists())
        self.assertFalse(list(cikti.parent.glob("*.yaziliyor")), "yarım dosya kalmaz")

    def test_bozuk_bloklar_kayitta_ve_uyarida(self):
        metin, cikti = self.eser(paragraf_sayisi=2, boy=50)
        cikti.parent.mkdir(parents=True)
        self.okuyucu(SahteTTS(), kalite=lambda s: (3.5, 2.2)).eseri_oku(metin, cikti)
        kalite = json.loads((cikti.parent / "kalite.json").read_text())
        self.assertEqual([k["bozuk"] for k in kalite], [True] * len(kalite))
        self.assertIn(f"SES KALİTESİ DÜŞÜK bloklar: {list(range(1, len(kalite) + 1))}", self.mesajlar)

    def test_bozuk_blok_yoksa_uyari_yazilmaz(self):
        metin, cikti = self.eser(paragraf_sayisi=2, boy=50)
        cikti.parent.mkdir(parents=True)
        self.okuyucu(SahteTTS()).eseri_oku(metin, cikti)
        self.assertFalse(any("SES KALİTESİ DÜŞÜK" in m for m in self.mesajlar))


class YamaDenemesiTesti(OkuyucuTabani):
    """Eşiği tutmayan ama iyi okunmuş blok önce yamayla onarılır: tek istek, ölçüm kaydında "yama"."""

    def blok(self, yamala, olcumler):
        olc = iter(olcumler)
        self.tts = SahteTTS()
        o = self.okuyucu(self.tts, olc=lambda m, s: next(olc), yamala=yamala)
        return o.seslendir("Bir iki üç dört beş.", "[1]")

    def test_basarili_yama_tek_istek_butcesiyle_ve_olcum_kaydi(self):
        istekler = []

        def yamala(metin, ses_, uret, esik, bildir):
            istekler.append(uret("Bir iki."))
            return ses(2.0)
        sonuc = self.blok(yamala, [(0.90, ["iki üç dört"]), (0.991, [])])
        self.assertEqual(len(sonuc), int(2.0 * SR))
        self.assertEqual(self.tts.butceler, [O.TEK_ISTEK_BUTCESI, 1], "yama isteği tek hak")
        self.assertIn("[1] yamalı: eşleşme 0.991", self.mesajlar)
        son = json.loads(self.y.olcum.read_text().splitlines()[-1])
        self.assertEqual({k: v for k, v in son.items() if k != "zaman"},
                         {"model": "m1", "kr": len("Bir iki üç dört beş."), "sn": 2.0, "oran": 0.991, "iyi": True,
                          "atlama": 0, "yama": True})

    def test_esigi_tutmayan_yama_kullanilmaz_atlamasi_yazilir(self):
        sonuc = self.blok(lambda *a, **k: ses(1.0), [(0.90, ["x y z"]), (0.93, ["kalan söz"]), (0.99, [])])
        self.assertNotEqual(len(sonuc), int(1.0 * SR))
        self.assertIn("[1] yamalı: eşleşme 0.930, ATLAMA: ['kalan söz']", self.mesajlar)
        self.assertFalse(json.loads(self.y.olcum.read_text().splitlines()[1])["iyi"])

    def test_esik_tam_tutan_ama_atlamali_yama_kullanilmaz(self):
        sonuc = self.blok(lambda *a, **k: ses(1.0), [(0.90, ["x y z"]), (O.ESIK, ["söz"]), (0.99, [])])
        self.assertNotEqual(len(sonuc), int(1.0 * SR))
        self.setUp()  # temiz kök: önceki denemeler diskte (H-018) ve yeniden kullanılırdı
        sonuc = self.blok(lambda *a, **k: ses(1.0), [(0.90, ["x y z"]), (O.ESIK, [])])
        self.assertEqual(len(sonuc), int(1.0 * SR), "eşik tam tutuyor ve atlama yok: yama kullanılır")

    def test_kota_biterse_durur_baska_hata_eski_yola_doner(self):
        with self.assertRaises(G.KotaDoldu):
            self.blok(lambda *a, **k: (_ for _ in ()).throw(G.KotaDoldu("bitti")), [(0.90, ["x y z"])])
        self.setUp()

        def bozuk(*a, **k):
            raise ValueError("beklenmedik")
        self.blok(bozuk, [(0.90, ["x y z"]), (0.99, [])])
        self.assertIn("[1] yama yapılamadı: ValueError('beklenmedik')", self.mesajlar)
        self.assertEqual(len(self.tts.istekler), 2, "yama düşünce blok yeniden okunur")

    def test_yama_onaramazsa_yeniden_okunur(self):
        self.blok(lambda *a, **k: None, [(0.90, ["x y z"]), (0.99, [])])
        self.assertEqual(len(self.tts.istekler), 2)
        self.assertFalse(any("yamalı" in m for m in self.mesajlar))


class BolmeTesti(OkuyucuTabani):
    """Boş yanıtta blok, harf sayısının yarısından ikiye bölünür; yarılar ayrı okunur ve araya duraklama konur."""

    def bol(self, paragraflar):
        metin = "\n\n".join(paragraflar)
        self.tts = SahteTTS([G.BosYanit("x")])
        sonuc = self.okuyucu(self.tts).seslendir(metin, "[3]")
        return metin, sonuc

    def test_yari_noktasi_ve_yarilar(self):
        for boylar, sol in (([10, 10, 10, 100], 3), ([100, 10, 10, 10], 1), ([40, 40], 1), ([10, 50, 10], 1)):  # yarıya ulaşan paragraftan önce bölünür
            with self.subTest(boylar=boylar):
                self.setUp()
                ps = [chr(97 + i) * n for i, n in enumerate(boylar)]
                metin, sonuc = self.bol(ps)
                self.assertEqual(self.tts.istekler, [metin, "\n\n".join(ps[:sol]), "\n\n".join(ps[sol:])])
                self.assertIn(f"[3] ikiye bölünüyor ({len(metin)} kr)", self.mesajlar)
                sureler = [len(ses(max(0.5, len(m) / 150.0))) for m in self.tts.istekler[1:]]
                self.assertEqual(len(sonuc), sureler[0] + len(O.S.sessizlik(O.BLOK_ARASI)) + sureler[1])

    def test_yarilar_kendi_etiketiyle_ve_kendi_onbellek_dosyasiyla(self):
        metin, _ = self.bol(["a" * 30, "b" * 30])
        ayar = O.OkumaAyari(model="m1", ses="Fola", hedef_sn=60)
        for yari in ("a" * 30, "b" * 30):
            self.assertTrue(O.blok_dosyasi(self.y.parcalar, yari, ayar).exists())
        self.assertTrue(any(m.startswith("[3]a ") for m in self.mesajlar))
        self.assertTrue(any(m.startswith("[3]b ") for m in self.mesajlar))


class UyarlamaliPlanTesti(OkuyucuTabani):
    def test_blok_siniri_okumadan_once_kaydedilir_ertesi_gun_ayni_bloklar(self):
        metin, cikti = self.eser()
        cikti.parent.mkdir(parents=True)
        dun = SahteTTS([None, G.KotaDoldu("bitti")])
        with self.assertRaises(G.KotaDoldu):
            self.okuyucu(dun).eseri_oku(metin, cikti)
        plan = json.loads((cikti.parent / "blok-plan.json").read_text())
        self.assertEqual(len(plan["sinirlar"]), 2, "ikinci bloğun sınırı istekten önce yazıldı")
        bugun = SahteTTS()
        self.okuyucu(bugun).eseri_oku(metin, cikti)
        self.assertEqual(bugun.istekler[0], dun.istekler[1], "kota biten blok aynı metinle sürer")
        self.assertEqual(json.loads((cikti.parent / "blok-plan.json").read_text())["sinirlar"][:2], plan["sinirlar"])

    def test_ilk_blok_olculen_hizin_payiyla_sonra_gercek_hizla(self):
        from sesli import metin as M
        metin, cikti = self.eser(paragraf_sayisi=30, boy=300)
        cikti.parent.mkdir(parents=True)
        tts = SahteTTS(kr_sn=15.0)
        self.okuyucu(tts, hedef_sn=200).eseri_oku(metin, cikti)
        ilk_hedef = 200 * O.olcum.VARSAYILAN_HIZ * O.ILK_BLOK_PAYI
        self.assertLessEqual(len(tts.istekler[0]), ilk_hedef * 1.04 + 400)
        self.assertGreater(len(tts.istekler[1]), len(tts.istekler[0]), "ölçülen hız (15 kr/sn) payı aşıyor")
        self.assertLessEqual(max(len(m) for m in tts.istekler), M.EN_COK_KR)


if __name__ == "__main__":
    unittest.main()
