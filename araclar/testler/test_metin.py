from __future__ import annotations

import unittest

from testler import yardim  # noqa: F401  (yol ayarı)
from sesli import metin as M


class CumlelerTesti(unittest.TestCase):
    def test_noktalama_ve_tirnaktan_boler(self):
        self.assertEqual(M.cumleler('Bir. İki! "Üç?" Dört… Beş'), ["Bir.", "İki!", '"Üç?"', "Dört…", "Beş"])

    def test_paragraf_arasindan_boler(self):
        self.assertEqual(M.cumleler("a b\n\nc d"), ["a b", "c d"])


class SabitBloklarTesti(unittest.TestCase):
    def test_bosluklari_sadelestirir_ve_sessiz_satiri_atar(self):
        yazi = "Bir  iki\nüç.\n\n— .....\n\nDört\xadbeş."
        self.assertEqual(M.sabit_bloklar(yazi), ["Bir iki üç.\n\nDörtbeş."])

    def test_esit_boylu_bloklar(self):
        par = ["x" * 3000] * 6  # 18000+ kr, sınır 8500 → 3 blok × 2 paragraf (8500 + 559 değil)
        bloklar = M.sabit_bloklar("\n\n".join(par), en_cok=8500)
        self.assertEqual([b.count("\n\n") + 1 for b in bloklar], [2, 2, 2])

    def test_siirde_satir_sonlari_korunur(self):
        self.assertEqual(M.sabit_bloklar("Dize bir\n  dize  iki", siir=True), ["Dize bir\ndize iki"])


class ParagraflarTesti(unittest.TestCase):
    def test_uzun_paragraf_cumle_sinirindan_parcalanir(self):
        cumle = "Bu bir cümledir. "
        uzun = (cumle * 40).strip()  # 679 kr
        par = M.paragraflar(uzun, en_cok=300)
        self.assertGreater(len(par), 1)
        self.assertFalse(par[0].devam)
        self.assertTrue(all(p.devam for p in par[1:]))
        self.assertEqual(M.birlestir(par), uzun)

    def test_birlestir_paragraf_bosluklarini_korur(self):
        par = [M.Paragraf("a", False), M.Paragraf("b", True), M.Paragraf("c", False)]
        self.assertEqual(M.birlestir(par), "a b\n\nc")


class SonrakiSinirTesti(unittest.TestCase):
    def setUp(self):
        self.par = [M.Paragraf("x" * 1000, False) for _ in range(30)]  # 30000 kr

    def test_kalan_hedefe_sigarsa_hepsi_tek_blok(self):
        self.assertEqual(M.sonraki_sinir(self.par, 25, hiz=10, hedef_sn=600), 30)

    def test_kalan_esit_paylasilir(self):
        # hedef 6000 kr → 5 eşit blok, her biri 6 paragraf
        self.assertEqual(M.sonraki_sinir(self.par, 0, hiz=10, hedef_sn=600), 6)

    def test_istek_siniri_asilmaz(self):
        j = M.sonraki_sinir(self.par, 0, hiz=100, hedef_sn=1200)  # hedef 120000 → EN_COK_KR'ye kısılır
        self.assertLessEqual(sum(len(p.metin) for p in self.par[:j]), M.EN_COK_KR)

    def test_tek_paragraf_hedefi_assa_da_ilerler(self):
        par = [M.Paragraf("x" * 9000, False), M.Paragraf("y" * 9000, False), M.Paragraf("z", False)]
        self.assertEqual(M.sonraki_sinir(par, 0, hiz=1, hedef_sn=100), 1)


if __name__ == "__main__":
    unittest.main()
