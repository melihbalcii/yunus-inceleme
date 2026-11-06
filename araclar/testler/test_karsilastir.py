from __future__ import annotations

import unittest

from testler import yardim  # noqa: F401
from sesli import karsilastir as K


class SayiTesti(unittest.TestCase):
    def test_okunuslar(self):
        self.assertEqual(K.sayi(0), "sıfır")
        self.assertEqual(K.sayi(40), "kırk")
        self.assertEqual(K.sayi(100), "yüz")
        self.assertEqual(K.sayi(1915), "bin dokuz yüz on beş")
        self.assertEqual(K.sayi(2_000_000), "iki milyon")


class KelimelerTesti(unittest.TestCase):
    def test_turkce_kucuk_harf_ve_rakam(self):
        self.assertEqual(K.kelimeler("İstanbul'da 3 IRMAK"), ["istanbul", "da", "üç", "ırmak"])

    def test_sade_kelimeler_sapkayi_atar(self):
        self.assertEqual(K.sade_kelimeler("Hâlâ îmân ûmumî"), ["hala", "iman", "umumi"])


class DuyulaniAritTesti(unittest.TestCase):
    def test_sira_ve_uydurma(self):
        self.assertEqual(K.duyulani_arit("4. Bölüm. Altyazı M.K."), "dördüncü Bölüm.  ")


class AtlamaTesti(unittest.TestCase):
    def test_yazim_farki_atlama_sayilmaz(self):
        self.assertFalse(K.kayip_mi(["hacegan", "dan"], ["hacegandan"]))

    def test_uc_kelimelik_eksik_atlamadir(self):
        metin = "kızı duyunca babasının ölüsüne gider ve ağlar"
        duyulan = "kızı ve ağlar"
        oran, atla = K.olcum(metin, duyulan)
        self.assertLess(oran, 0.9)
        self.assertEqual(atla, ["duyunca babasının ölüsüne gider"])

    def test_okunamaz_buyu_sozleri_atlama_sayilmaz(self):
        self.assertFalse(K.kayip_mi(["fınglui", "mıglunaf", "kutulu"], []))

    def test_tam_okuma(self):
        oran, atla = K.olcum("Bir iki üç dört beş altı.", "Bir, iki, üç, dört, beş, altı.")
        self.assertEqual((oran, atla), (1.0, []))


class YazimFarkiTesti(unittest.TestCase):
    def test_harfleri_tutan_ama_farkli_bolunmus_sozler_atlama_degil(self):
        self.assertFalse(K.kayip_mi(["a", "b", "c", "d", "e", "fghijklmno"], ["abcdefghijklmno"]))
        self.assertTrue(K.kayip_mi(["a", "b", "c", "d", "e", "fghijklmno"], ["xyz"]))


class KarsilastirmaSinirTesti(unittest.TestCase):
    def test_sayi_okunuslari_tablosu(self):
        for n, ok in ((9, "dokuz"), (10, "on"), (15, "on beş"), (20, "yirmi"), (99, "doksan dokuz"), (101, "yüz bir"),
                      (115, "yüz on beş"), (200, "iki yüz"), (1000, "bin"), (2000, "iki bin"), (1_000_000, "bir milyon"),
                      (2_500_000, "iki milyon beş yüz bin"), ("7", "yedi"),
                      (123_456_789, "yüz yirmi üç milyon dört yüz elli altı bin yedi yüz seksen dokuz")):
            self.assertEqual(K.sayi(n), ok, n)

    def test_kelimeler_buyuk_I_ve_sapka(self):
        self.assertEqual(K.kelimeler("IŞIK İz Âlem 21"), ["ışık", "iz", "alem", "yirmi", "bir"])

    def test_sira_sozcugu_1_ile_20_arasi(self):
        self.assertEqual(K.sira_sozcuk("1. Bölüm"), "birinci Bölüm")
        self.assertEqual(K.sira_sozcuk("20. kısım"), "yirminci kısım")
        self.assertEqual(K.sira_sozcuk("12. Masal ve 3. öykü"), "on ikinci Masal ve üçüncü öykü")
        for degismez in ("21. Bölüm", "0. Bölüm", "4. sayfa", "4.Bölümde"[:0] + "x4. Bölüm"):
            self.assertEqual(K.sira_sozcuk(degismez), degismez)

    def test_uydurma_altyazilar_silinir(self):
        for kalip in ("Altyazı M.K.", "İzlediğiniz için teşekkür ederim.", "Abone olmayı unutmayın.",
                      "Bu dizinin betimlemesi şöyledir."):
            self.assertEqual(K.duyulani_arit(f"Son söz. {kalip}").strip(), "Son söz.", kalip)

    def test_atlama_esikleri_sinirda(self):
        self.assertTrue(K.kayip_mi(["bir", "iki", "uçak"], []), "3 kelime, 10 harf: atlama")
        self.assertFalse(K.kayip_mi(["bir", "iki", "üç"], []), "3 kelime ama 8 harf")
        self.assertFalse(K.kayip_mi(["birinci", "ikinciler"], []), "2 kelime")
        self.assertTrue(K.kayip_mi(["fınglui", "kapı", "pencere", "duvar"], []), "okunamazlar üçte ikiden az")
        self.assertFalse(K.kayip_mi(["fınglui", "mıglunaf", "pencereler"], []), "okunamazlar üçte iki")

    def test_harf_eslesmesi_sayilari(self):
        oran, eslesen, harf = K.harf_eslesmesi("Bir iki üç dört", "bir iki")
        self.assertEqual((eslesen, harf), (6, 12))
        self.assertAlmostEqual(oran, 2 * 6 / (12 + 6))
        self.assertEqual(K.harf_eslesmesi("Kapı", "Altyazı M.K."), (0.0, 0, 4))

    def test_degistirilen_parca_da_atlama_olabilir(self):
        self.assertEqual(K.atlamalar(["a", "kapıyı", "açtı", "ve", "çıktı", "b"], ["a", "x", "b"]),
                         ["kapıyı açtı ve çıktı"])


if __name__ == "__main__":
    unittest.main()
