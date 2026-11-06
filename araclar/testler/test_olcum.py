"""Ölçüm kaydı: okuma hızı ve başarı oranı planlamayı (blok boyu, araç seçimi) belirler; istek özeti kotayı izler."""
from __future__ import annotations

import datetime as dt
import json
import unittest
from pathlib import Path

from testler.yardim import GeciciKokTesti
from sesli import olcum as O
from sesli.kota import kota_gunu


class OlcumKaydiTesti(GeciciKokTesti):
    def setUp(self) -> None:
        super().setUp()
        self.dosya = self.y.olcum

    def kayit(self, *satirlar: dict) -> None:
        self.dosya.write_text("".join(json.dumps(s) + "\n" for s in satirlar))

    def test_oku_yoksa_bos_bozuk_ve_bos_satiri_atlar(self):
        self.assertEqual(O.oku(self.dosya), [])
        self.dosya.write_text('{"a": 1}\n\n{yarım\n   \n{"b": 2}\n')
        self.assertEqual(O.oku(self.dosya), [{"a": 1}, {"b": 2}])

    def test_yaz_satir_ekler_yazamazsa_durmaz(self):
        O.yaz(self.dosya, "m1", kr=10, iyi=True)
        O.yaz(self.dosya, "m2", sn=1.5)
        a, b = O.oku(self.dosya)
        self.assertRegex(a.pop("zaman"), r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        self.assertEqual(a, {"model": "m1", "kr": 10, "iyi": True})
        self.assertEqual({k: v for k, v in b.items() if k != "zaman"}, {"model": "m2", "sn": 1.5})
        O.yaz(Path("/olmayan/klasor/x.jsonl"), "m1", kr=1)  # hata fırlatmamalı

    def test_hiz_az_ornekte_varsayilan(self):
        self.kayit(*[{"model": "m1", "kr": 2000, "sn": 100, "iyi": True}] * 2)
        self.assertEqual(O.model_hizi(self.dosya, "m1"), O.VARSAYILAN_HIZ)

    def test_hiz_yalniz_iyi_uzun_ve_ayni_modelin_son_40_denemesinin_medyani(self):
        eski = [{"model": "m1", "kr": 9000, "sn": 100, "iyi": True}] * 5          # son 40'ın dışında kalır
        gecerli = [{"model": "m1", "kr": 1000 + 10 * i, "sn": 100, "iyi": True} for i in range(40)]
        disarida = [{"model": "m2", "kr": 5000, "sn": 100, "iyi": True},          # başka model
                    {"model": "m1", "kr": 5000, "sn": 100, "iyi": False},         # kötü okuma
                    {"model": "m1", "kr": 5000, "sn": 60, "iyi": True}]           # tam 60 sn: güvenilmez
        self.kayit(*eski, *gecerli, *disarida)
        self.assertEqual(O.model_hizi(self.dosya, "m1"), (1000 + 10 * 20) / 100)

    def test_basari_orani(self):
        self.assertEqual(O.basari_orani(self.dosya, "m1"), O.VARSAYILAN_BASARI)
        self.kayit(*[{"model": "m1", "iyi": False}] * 10,                         # son 40'ın dışında
                   *[{"model": "m1", "iyi": i % 4 != 0} for i in range(40)],
                   {"model": "m1", "iyi": False, "yama": True}, {"model": "m2", "iyi": False})
        self.assertEqual(O.basari_orani(self.dosya, "m1"), 30 / 40)
        self.kayit(*[{"model": "m1", "iyi": True}] * 4)
        self.assertEqual(O.basari_orani(self.dosya, "m1"), O.VARSAYILAN_BASARI, "4 örnek yetmez")


class IstekOzetiTesti(GeciciKokTesti):
    def test_yalniz_istenen_kota_gununu_sayar_bozuk_kaydi_atlar(self):
        simdi = dt.datetime.now().astimezone()
        dun = simdi - dt.timedelta(days=1)
        z = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")  # noqa: E731
        satirlar = [{"zaman": z(simdi), "sonuc": "ses"}, {"zaman": z(simdi), "sonuc": "ses"},
                    {"zaman": z(simdi), "sonuc": "kayip"}, {"zaman": z(simdi)}, {"zaman": z(dun), "sonuc": "ses"},
                    {"zaman": "dün akşam", "sonuc": "ses"}, {"sonuc": "ses"}]
        self.y.istek_defteri.write_text("".join(json.dumps(s) + "\n" for s in satirlar))
        self.assertEqual(O.istek_ozeti(self.y.istek_defteri, kota_gunu(simdi)), {"ses": 2, "kayip": 1, "?": 1})
        self.assertEqual(O.istek_ozeti(self.y.istek_defteri, kota_gunu(dun)), {"ses": 1})

    def test_bosa_giden_kota_harcayip_ses_getirmeyenler(self):
        self.assertEqual(set(O.BOSA_GIDEN), {"kayip", "zaman_asimi", "bos", "guvenlik", "hata"})


if __name__ == "__main__":
    unittest.main()
