"""Okuyucu: sahte TTS, sahte Whisper ölçümü ve sahte kalite ölçümüyle (ağ ve model yok)."""
from __future__ import annotations

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


class OkuyucuTesti(GeciciKokTesti):
    def okuyucu(self, tts, *, olc=iyi_olcum, kalite=iyi_kalite, yamala=None, **ayar):
        a = O.OkumaAyari(model="m1", ses="Fola", **({"hedef_sn": 60} | ayar))
        self.mesajlar: list[str] = []
        return O.Okuyucu(tts, a, self.y, bildir=self.mesajlar.append, olc=olc, kalite=kalite,
                         yamala=yamala or (lambda *a, **k: None))

    def eser(self, paragraf_sayisi=12, boy=300):
        d = self.metin_yaz("kisa-oyku", [f"Paragraf {i}. " + "k" * boy for i in range(paragraf_sayisi)])
        return d, self.y.fola_klasoru("kisa-oyku") / "kisa-oyku.mp3"

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
        tts = SahteTTS()
        sure = self.okuyucu(tts).eseri_oku(metin, cikti)
        beklenen = sum(max(0.5, len(m) / 15.0) + O.BLOK_ARASI for m in tts.istekler) / 60
        self.assertAlmostEqual(sure, beklenen, delta=1 / SR)


if __name__ == "__main__":
    unittest.main()
