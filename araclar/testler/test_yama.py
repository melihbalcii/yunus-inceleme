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


if __name__ == "__main__":
    unittest.main()
