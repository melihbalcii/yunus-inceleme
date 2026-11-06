"""yama.yamala: atlanan cümle yerine konur, fazla okuma kesilir, güvenle onarılamayan blok için None döner.

Sesler yapaydır: her kelime 0,4 sn sabit genlik, aralarında 0,1 sn sessizlik. Kelime zamanları (Whisper yerine)
sesle birlikte üretilir; böylece çıkan sesin kelime sırası genliklerden okunabilir.
"""
from __future__ import annotations

import unittest

import numpy as np

import testler.yardim  # noqa: F401 — araclar/ yolunu ekler
from sesli import ses as S
from sesli.gemini import GuvenlikReddi
from sesli.yama import KelimeZamani, yamala

METIN = "Bir iki üç. Dört beş altı. Yedi sekiz dokuz."
KELIME, ARA = 0.4, 0.1


def konus(kelimeler: list[tuple[str, float]]) -> tuple[S.Dalga, list[KelimeZamani]]:
    """[(kelime, genlik)] → (ses, kelime zamanları)."""
    parcalar, zamanlar, t = [], [], 0.0
    for kelime, genlik in kelimeler:
        parcalar += [np.full(int(S.SR * KELIME), genlik, dtype=np.float32), S.sessizlik(ARA)]
        zamanlar.append((kelime, t, t + KELIME))
        t += KELIME + ARA
    return np.concatenate(parcalar), zamanlar


def sira(ses: S.Dalga) -> list[float]:
    """Sesteki kelimelerin genlikleri sırayla (sessizlikle ayrılan sabit bölümler)."""
    dolu = np.abs(ses) > 0.01
    baslar = np.flatnonzero(dolu & ~np.concatenate([[False], dolu[:-1]]))
    return [round(float(ses[i]), 2) for i in baslar]


class YamaTesti(unittest.TestCase):
    def setUp(self) -> None:
        self.zamanlar: dict[int, list[KelimeZamani]] = {}
        self.istekler: list[str] = []

    def kaydet(self, kelimeler: list[tuple[str, float]]) -> S.Dalga:
        ses, z = konus(kelimeler)
        self.zamanlar[id(ses)] = z
        return ses

    def yamala(self, ses: S.Dalga, uret: object = None) -> S.Dalga | None:
        def varsayilan_uret(metin: str) -> S.Dalga:
            self.istekler.append(metin)
            return self.kaydet([(k, 0.3) for k in ("dört", "beş", "altı")])
        return yamala(METIN, ses, uret or varsayilan_uret, esik=0.95, bildir=lambda s: None,  # type: ignore[arg-type]
                      kelime_zamanlari=lambda a: self.zamanlar[id(a)])

    def test_atlanan_cumle_tek_istekle_yerine_konur(self):
        ses = self.kaydet([(k, 0.5) for k in ("bir", "iki", "üç", "yedi", "sekiz", "dokuz")])
        sonuc = self.yamala(ses)
        self.assertEqual(self.istekler, ["Dört beş altı."])
        assert sonuc is not None
        self.assertEqual(sira(sonuc), [0.5] * 3 + [0.3] * 3 + [0.5] * 3)

    def test_fazla_okuma_istek_harcanmadan_kesilir(self):
        ekli = ([(k, 0.5) for k in ("bir", "iki", "üç")] + [(k, 0.7) for k in ("fazla", "ek", "söz", "burada")]
                + [(k, 0.5) for k in ("dört", "beş", "altı", "yedi", "sekiz", "dokuz")])
        sonuc = self.yamala(self.kaydet(ekli))
        self.assertEqual(self.istekler, [])
        assert sonuc is not None
        self.assertEqual(sira(sonuc), [0.5] * 9)

    def test_sorunsuz_blokta_yapacak_is_yok(self):
        tam = self.kaydet([(k, 0.5) for k in ("bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz")])
        self.assertIsNone(self.yamala(tam))
        self.assertEqual(self.istekler, [])

    def test_yama_istegi_reddedilirse_onarilmaz(self):
        def ret(metin: str) -> S.Dalga:
            raise GuvenlikReddi(len(metin))
        ses = self.kaydet([(k, 0.5) for k in ("bir", "iki", "üç", "yedi", "sekiz", "dokuz")])
        self.assertIsNone(self.yamala(ses, ret))

    def test_yama_da_yanlis_okunursa_onarilmaz(self):
        def yanlis(metin: str) -> S.Dalga:
            return self.kaydet([(k, 0.3) for k in ("dört", "başka", "şey")])
        ses = self.kaydet([(k, 0.5) for k in ("bir", "iki", "üç", "yedi", "sekiz", "dokuz")])
        self.assertIsNone(self.yamala(ses, yanlis))


class YamaParcalariTesti(unittest.TestCase):
    """yamala'nın adımları ayrı ayrı: kesim noktaları, bölge birleştirme, sesin yeniden kurulması."""

    def test_ara_nokta_kenarlarda_bas_ve_son_icte_duraklamanin_ortasi(self):
        from sesli.yama import _ara_nokta
        duy = [("a", 0.0, 0.4), ("b", 0.6, 1.0), ("c", 1.5, 1.9)]
        self.assertEqual(_ara_nokta(duy, 0, 3.0), 0.0)
        self.assertEqual(_ara_nokta(duy, -1, 3.0), 0.0)
        self.assertEqual(_ara_nokta(duy, 3, 3.0), 3.0)
        self.assertEqual(_ara_nokta(duy, 1, 3.0), 0.5)
        self.assertEqual(_ara_nokta(duy, 2, 3.0), 1.25)

    def test_kelimeler_her_kelimenin_parcasini_bilir(self):
        from sesli.yama import _kelimeler
        self.assertEqual(_kelimeler(["Bir iki.", "", "Üç!"]), (["bir", "iki", "üç"], [0, 0, 2]))

    def test_bitisik_atlanan_cumleler_tek_bolge_olur(self):
        from sesli.yama import _Dinleme, _eksik_ve_fazla, _eslestir, _kelimeler
        cumle = ["Bir iki üç.", "Dört beş altı.", "Yedi sekiz dokuz.", "On on bir on iki."]
        hedef, hangi = _kelimeler(cumle)
        sozler = ["bir", "iki", "üç", "on", "on", "bir", "on", "iki"]  # 2. ve 3. cümle hiç okunmamış
        duy = [(w, i * 1.0, i * 1.0 + 0.8) for i, w in enumerate(sozler)]
        bolgeler, atilacak = _eksik_ve_fazla(_eslestir(hedef, duy), hedef, hangi, _Dinleme(duy, len(duy) * 1.0))
        self.assertEqual(bolgeler, [[1, 2]], "atlanan 2. ve 3. cümle bitişik: tek bölge")
        self.assertEqual(atilacak, [])

    def test_kisa_fazla_okuma_kesilmez_uzunu_kesilir(self):
        from sesli.yama import _Dinleme, _eksik_ve_fazla, _eslestir, _kelimeler
        hedef, hangi = _kelimeler(["Bir iki üç dört."])
        for ek, beklenen in ((["eee"], []), (["burada", "fazladan", "okunmuş", "sözler"], [(1.9, 5.9)])):
            sozler = ["bir", "iki", *ek, "üç", "dört"]
            duy = [(w, i * 1.0, i * 1.0 + 0.8) for i, w in enumerate(sozler)]
            _, atilacak = _eksik_ve_fazla(_eslestir(hedef, duy), hedef, hangi, _Dinleme(duy, 10.0))
            self.assertEqual([(round(a, 2), round(b, 2)) for a, b in atilacak], beklenen, ek)

    def test_cok_fazla_bolge_onarilmaz(self):
        from sesli.yama import EN_COK_YER, _Dinleme, _kesimler
        bolgeler = [[i * 2, i * 2] for i in range(EN_COK_YER + 1)]
        self.assertIsNone(_kesimler(bolgeler, [0], {}, _Dinleme([], 1.0), ["x"]))

    def test_birlestir_yamayi_yerine_koyar_cakisani_reddeder(self):
        from sesli.yama import _Kesim, _birlestir
        sr = S.SR
        ses = np.concatenate([np.full(sr, 0.1), np.full(sr, 0.2), np.full(sr, 0.3)]).astype(np.float32)
        yama = np.full(sr // 2, 0.9, dtype=np.float32)
        sonuc = _birlestir(ses, [_Kesim(1.0, 2.0, "x", yama)])
        assert sonuc is not None
        bosluk = len(S.sessizlik(0.25))
        self.assertEqual(len(sonuc), 2 * sr + 2 * bosluk + len(yama))
        self.assertEqual(sira(sonuc), [0.1, 0.9, 0.3])  # sira() iki basamağa yuvarlar
        bas = _birlestir(ses, [_Kesim(0.0, 1.0, "x", yama)])  # en başta: önüne sessizlik konmaz
        assert bas is not None
        self.assertAlmostEqual(float(bas[0]), 0.9, places=5)
        self.assertEqual(len(bas), 2 * sr + bosluk + len(yama))
        kes = _birlestir(ses, [_Kesim(2.0, 3.0)])  # yalnız kesme
        assert kes is not None
        self.assertEqual(len(kes), 2 * sr)
        self.assertIsNone(_birlestir(ses, [_Kesim(0.5, 1.5), _Kesim(1.0, 2.0)]), "çakışan kesimler")


class EksikFazlaSinirTesti(unittest.TestCase):
    def ayir(self, cumle, sozler):
        from sesli.yama import _Dinleme, _eksik_ve_fazla, _eslestir, _kelimeler
        hedef, hangi = _kelimeler(cumle)
        duy = [(w, i * 1.0, i * 1.0 + 0.8) for i, w in enumerate(sozler)]
        return _eksik_ve_fazla(_eslestir(hedef, duy), hedef, hangi, _Dinleme(duy, len(duy) * 1.0))

    def test_fazla_okuma_hem_4_kelime_hem_15_harf_olmali(self):
        cumle = ["Bir iki üç dört."]
        for ek, kesilir in ((["aa", "bb", "cc", "dd"], False), (["uzunsöz", "uzunsöz", "uzunsöz"], False),
                            (["aaaa", "bbbb", "cccc", "ddd"], True)):
            with self.subTest(ek=ek):
                _, atilacak = self.ayir(cumle, ["bir", "iki", *ek, "üç", "dört"])
                self.assertEqual(bool(atilacak), kesilir)

    def test_atlanan_bolgeler_bitisikse_birlesir_degilse_ayri(self):
        cumle = ["Bir iki üç.", "Dört beş altı.", "Yedi sekiz dokuz.", "On on bir on iki.", "Son cümle burada."]
        bitisik, _ = self.ayir(cumle, ["bir", "iki", "üç", "son", "cümle", "burada"])
        self.assertEqual(bitisik, [[1, 3]])
        ayri, _ = self.ayir(cumle, ["bir", "iki", "üç", "yedi", "sekiz", "dokuz", "son", "cümle", "burada"])
        self.assertEqual(ayri, [[1, 1], [3, 3]])


class BolgeVeKesimTesti(unittest.TestCase):
    def ayir(self, cumle, sozler):
        from sesli.yama import _Dinleme, _eksik_ve_fazla, _eslestir, _kelimeler, _kesimler
        hedef, hangi = _kelimeler(cumle)
        duy = [(w, i * 1.0, i * 1.0 + 0.8) for i, w in enumerate(sozler)]
        d = _Dinleme(duy, len(duy) * 1.0)
        es = _eslestir(hedef, duy)
        bolgeler, atilacak = _eksik_ve_fazla(es, hedef, hangi, d)
        return bolgeler, _kesimler([list(b) for b in bolgeler], hangi, es[1], d, cumle)

    def test_iki_ayri_atlama_yan_yanaysa_birlesir(self):
        cumle = ["Bir iki üç.", "Dört beş altı.", "Yedi sekiz dokuz onlar.", "Son söz burada."]
        bolgeler, kesim = self.ayir(cumle, ["bir", "iki", "üç", "yedi", "son", "söz", "burada"])
        self.assertEqual(bolgeler, [[1, 2]], "Dört beş altı + sekiz dokuz onlar")
        (k,) = kesim
        # arada duyulmuş "yedi" de kesilir: cümle yamada baştan okunacak, iki kez duyulmasın
        self.assertEqual((k.t0, k.t1, k.yazi), (2.9, 3.9, "Dört beş altı. Yedi sekiz dokuz onlar."))

    def test_baska_soz_okunan_yer_de_atlamadir(self):
        cumle = ["Bir iki üç.", "Dört beş altı yedi sekiz.", "Son söz burada."]
        bolgeler, _ = self.ayir(cumle, ["bir", "iki", "üç", "zzz", "son", "söz", "burada"])
        self.assertEqual(bolgeler, [[1, 1]])

    def test_bastaki_ve_sondaki_atlamanin_kesimi(self):
        cumle = ["Dört beş altı.", "Bir iki üç.", "Yedi sekiz dokuz."]
        _, kesim = self.ayir(cumle, ["bir", "iki", "üç"])
        self.assertEqual([(k.t0, k.t1, k.yazi) for k in kesim],
                         [(0.0, 0.0, "Dört beş altı."), (3.0, 3.0, "Yedi sekiz dokuz.")])  # baştan ve sona eklenir

    def test_cevresi_karisik_bolge_onarilmaz(self):
        from sesli.yama import _Dinleme, _kesimler
        duy = [("a", 0.0, 0.5), ("b", 1.0, 1.5)]
        self.assertIsNone(_kesimler([[1, 1]], [0, 1, 2], {0: 1, 2: 0}, _Dinleme(duy, 2.0), ["A.", "B.", "C."]))


class YamaOkumaTesti(unittest.TestCase):
    """_yamayi_oku: birden çok atlanan yer tek istekte okunur, ses yerlerine göre doğru noktadan bölünür."""

    def oku(self, yazilar, sozler, esik=0.95, uret=None):
        from sesli.yama import _yamayi_oku
        ses_, zaman = konus(sozler)
        self.mesajlar: list[str] = []
        self.istenen: list[str] = []

        def varsayilan(m):
            self.istenen.append(m)
            return ses_
        return _yamayi_oku(yazilar, uret or varsayilan, esik, self.mesajlar.append, lambda s: zaman)

    def test_iki_yer_tek_istekte_okunur_dogru_bolunur(self):
        parcalar = self.oku(["Bir iki.", "Üç dört."], [("bir", 0.1), ("iki", 0.2), ("üç", 0.3), ("dört", 0.4)])
        assert parcalar is not None
        self.assertEqual(self.istenen, ["Bir iki.\n\nÜç dört."])
        self.assertEqual([sira(p) for p in parcalar], [[0.1, 0.2], [0.3, 0.4]])
        uzunluk = len(konus([("x", 0.1)] * 4)[0]) / S.SR
        self.assertEqual(self.mesajlar, [f"   yama: 2 yer, 18 kr tek istekte, {uzunluk:.1f} sn, eşleşme 1.000"])

    def test_esik_ve_atlama(self):
        self.assertIsNone(self.oku(["Bir iki üç dört beş."], [("bir", 0.1), ("iki", 0.2)], esik=0.95))
        self.assertIn("eşleşme", self.mesajlar[0])
        self.assertIsNone(self.oku(["Bir iki üç kapıyı açtı."], [("bir", 0.1)], esik=0.0))
        self.assertIn("ATLAMA: ['iki üç kapıyı açtı']", self.mesajlar[0])
        self.assertIsNotNone(self.oku(["Bir iki."], [("bir", 0.1), ("iki", 0.2)], esik=1.0), "tam eşik tutar")

    def test_bos_yanit_ve_guvenlik_reddi_onarilamaz(self):
        from sesli.gemini import BosYanit
        for hata in (BosYanit("x"), GuvenlikReddi(10)):
            def uret(m, h=hata):
                raise h
            self.assertIsNone(self.oku(["Bir."], [("bir", 0.1)], uret=uret))
            self.assertEqual(self.mesajlar, [])

    def test_yerlerin_sirasi_karisirsa_onarilmaz(self):
        self.assertIsNone(self.oku(["Bir iki.", "Üç dört."], [("üç", 0.3), ("dört", 0.4), ("bir", 0.1), ("iki", 0.2)],
                                   esik=0.0))


if __name__ == "__main__":
    unittest.main()
