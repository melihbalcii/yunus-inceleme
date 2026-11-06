from __future__ import annotations

import json
import unittest

from testler.yardim import GeciciKokTesti
from sesli import ceviri as C


class SiraTesti(unittest.TestCase):
    def test_roma(self):
        self.assertEqual([C.roma(x) for x in ("I", "IV", "IX", "XIV", "XL", "XLVI", "XC")], [1, 4, 9, 14, 40, 46, 90])

    def test_sirali_turkce_buyuk_harf(self):
        self.assertEqual(C.sirali(1), "Birinci")
        self.assertEqual(C.sirali(2), "İkinci")  # str.upper "Ikinci" yapıyordu
        self.assertEqual(C.sirali(46), "Kırk altıncı")
        self.assertEqual(C.sirali(10), "Onuncu")
        with self.assertRaises(C.CeviriHatasi):
            C.sirali(100)

    def test_okunus_tam_sozcukte(self):
        okunus = (("Joe", "Co"), ("Eden", "İdın"))
        self.assertEqual(C.okunusla("Joe'nun Joey'i Eden Edenic\n", okunus), "Co'nun Joey'i İdın Edenic\n")


class BirlestirmeTesti(GeciciKokTesti):
    def kur(self, bolumler: list[str], **ayar):
        k = self.y.eser_klasoru("ceviri-eseri")
        (k / "tr").mkdir(parents=True)
        for i, b in enumerate(bolumler, 1):
            (k / "tr" / f"{i:02d}.md").write_text(b, encoding="utf-8")
        v = {"bolum_sayisi": len(bolumler), "giris": "Eser. Yazar.", "kapanis": ["Son."],
             "okunus": [["Smith", "Smit"]], **ayar}
        (k / "ceviri.json").write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
        return k

    def test_basliklar_ve_okunus(self):
        k = self.kur(["## Birinci Kısım\n\n### I\nYol\n\nSmith geldi.", "### II\n\nSmith gitti."],
                     ceviri_basligi="# Eser")
        ceviri, ses = C.birlestir(k, C.CeviriAyari.oku(k / "ceviri.json"))
        self.assertTrue(ceviri.startswith("# Eser\n\n## Birinci Kısım\n\n### I\nYol\n\nSmith geldi."))
        self.assertEqual(ses, "Eser. Yazar.\n\nBirinci kısım.\n\nBirinci bölüm: Yol.\n\nSmit geldi.\n\n"
                              "İkinci bölüm.\n\nSmit gitti.\n\nSon.\n")

    def test_bolum_sirasi_bozuksa_hata(self):
        k = self.kur(["### I\n\na", "### III\n\nb"])
        with self.assertRaises(C.CeviriHatasi):
            C.birlestir(k, C.CeviriAyari.oku(k / "ceviri.json"))

    def test_kisimda_numara_bastan_baslar(self):
        k = self.kur(["## Birinci Kısım\n\n### I\n\na\n\n## İkinci Kısım\n\n### I\n\nb"])
        _, ses = C.birlestir(k, C.CeviriAyari.oku(k / "ceviri.json"))
        self.assertEqual(ses.count("Birinci bölüm."), 2)

    def test_taninmayan_baslik_hata(self):
        k = self.kur(["#### dipnot\n\na"])
        with self.assertRaises(C.CeviriHatasi):
            C.birlestir(k, C.CeviriAyari.oku(k / "ceviri.json"))

    def test_eksik_bolum_dosyasi(self):
        k = self.kur(["### I\n\na"], bolum_sayisi=2)
        with self.assertRaises(C.CeviriHatasi):
            C.birlestir(k, C.CeviriAyari.oku(k / "ceviri.json"))

    def test_yaz(self):
        self.kur(["### I\n\nSmith."])
        paragraf, kelime = C.yaz("ceviri-eseri", self.y)
        self.assertEqual((paragraf, kelime), (4, 6))
        self.assertTrue((self.y.eser_klasoru("ceviri-eseri") / "ceviri.txt").exists())


class CeviriAyariTesti(GeciciKokTesti):
    def test_varsayilanlar_ve_eksik_alan(self):
        d = self.kok / "ceviri.json"
        d.write_text(json.dumps({"bolum_sayisi": "2", "giris": "G.", "kapanis": ["K1.", "K2."]}), encoding="utf-8")
        a = C.CeviriAyari.oku(d)
        self.assertEqual((a.bolum_sayisi, a.giris, a.kapanis, a.okunus, a.ceviri_basligi), (2, "G.", ("K1.", "K2."), (), ""))
        for icerik in ("{bozuk", json.dumps({"giris": "G.", "kapanis": []}), json.dumps({"bolum_sayisi": "iki",
                       "giris": "G.", "kapanis": []}), json.dumps({"bolum_sayisi": 1, "giris": "G.", "kapanis": [],
                       "okunus": [["tek"]]})):
            d.write_text(icerik, encoding="utf-8")
            with self.subTest(icerik=icerik), self.assertRaises(C.CeviriHatasi):
                C.CeviriAyari.oku(d)
        with self.assertRaises(C.CeviriHatasi):
            C.CeviriAyari.oku(self.kok / "yok.json")

    def test_basliksiz_ceviri_ve_yumusak_tire(self):
        k = self.kok / "e"
        (k / "tr").mkdir(parents=True)
        (k / "tr" / "01.md").write_text("Bir\xadlikte.\n\nİki.", encoding="utf-8")
        ceviri, ses = C.birlestir(k, C.CeviriAyari(1, "Giriş.", ("K1.", "K2."), ()))
        self.assertEqual(ceviri, "Bir\xadlikte.\n\nİki.\n")
        self.assertEqual(ses, "Giriş.\n\nBirlikte.\n\nİki.\n\nK1.\n\nK2.\n")


if __name__ == "__main__":
    unittest.main()
