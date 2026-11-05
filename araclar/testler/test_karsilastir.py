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


if __name__ == "__main__":
    unittest.main()
