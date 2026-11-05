from __future__ import annotations

import json
import threading
import unittest

from testler.yardim import GeciciKokTesti
from sesli.ayar import AyarHatasi, env_oku, gerekli
from sesli.durum import DurumDeposu
from sesli.katalog import EserDurumu, Katalog, KatalogHatasi


class KatalogTesti(GeciciKokTesti):
    def test_yukler_ve_sorgular(self):
        k = Katalog.yukle(self.y)
        self.assertEqual(len(k), 4)
        self.assertEqual(k.al("kisa-oyku").dosya_adi, "01 - Kısa Öykü - Yazar Bir.mp3")
        self.assertIs(k.al("birakilan").durum, EserDurumu.VAZGECILDI)
        self.assertEqual([e.ad for e in k.etkinler()], ["kisa-oyku", "uzun-roman", "emel-eseri"])
        self.assertEqual(k.numarayla(2).ad, "uzun-roman")
        self.assertIsNone(k.numarayla(99))

    def test_ayni_numara_reddedilir(self):
        self.eser_listesi_yaz([{"ad": "a", "no": 1, "eser": "A", "yazar": "X", "durum": "etkin"},
                               {"ad": "b", "no": 1, "eser": "B", "yazar": "X", "durum": "etkin"}])
        with self.assertRaises(KatalogHatasi):
            Katalog.yukle(self.y)

    def test_gecersiz_durum_reddedilir(self):
        self.eser_listesi_yaz([{"ad": "a", "no": 1, "eser": "A", "yazar": "X", "durum": "belki"}])
        with self.assertRaises(KatalogHatasi):
            Katalog.yukle(self.y)

    def test_olmayan_eser(self):
        with self.assertRaises(KatalogHatasi):
            Katalog.yukle(self.y).al("yok")


class AyarTesti(GeciciKokTesti):
    def test_env_okuma(self):
        d = self.kok / ".env"
        d.write_text('# yorum\nA=1\nexport B="iki = 2"\n\nC=\'üç\'\nbozuk satır\n', encoding="utf-8")
        self.assertEqual(env_oku(d), {"A": "1", "B": "iki = 2", "C": "üç"})
        self.assertEqual(gerekli(d, "A"), "1")
        with self.assertRaises(AyarHatasi):
            gerekli(d, "YOK")
        self.assertEqual(env_oku(self.kok / "olmayan"), {})


class DurumDeposuTesti(GeciciKokTesti):
    def test_bos_dosya(self):
        d = DurumDeposu(self.y.durum).oku()
        self.assertEqual((d.atama, d.ret, d.oncelik), ({}, {}, []))

    def test_degisiklik_yazilir_bilinmeyen_alan_korunur(self):
        self.y.durum.write_text(json.dumps({"atama": {"a": "m1"}, "elle": {"x": 1}}))
        depo = DurumDeposu(self.y.durum)
        with depo.degistir() as d:
            d.reddet("m1", "a")
            d.reddet("m1", "a")  # iki kez eklenmez
        veri = json.loads(self.y.durum.read_text())
        self.assertEqual(veri["atama"], {})
        self.assertEqual(veri["ret"], {"m1": ["a"]})
        self.assertEqual(veri["elle"], {"x": 1})

    def test_hata_olursa_yazilmaz(self):
        depo = DurumDeposu(self.y.durum)
        with self.assertRaises(RuntimeError):
            with depo.degistir() as d:
                d.atama["a"] = "m"
                raise RuntimeError
        self.assertFalse(self.y.durum.exists())

    def test_dis_degisiklik_ezilmez(self):
        """Eski programın hatası: bellekteki kopya, dosyaya sonradan eklenen ortak ayarını siliyordu."""
        depo = DurumDeposu(self.y.durum)
        with depo.degistir() as d:
            d.atama["a"] = "m1"
        veri = json.loads(self.y.durum.read_text())  # program çalışırken elle düzenleme
        veri["ortak"] = {"a": ["m2"]}
        self.y.durum.write_text(json.dumps(veri))
        with depo.degistir() as d:
            d.atama["b"] = "m1"
        son = depo.oku()
        self.assertEqual(son.ortak, {"a": ["m2"]})
        self.assertEqual(son.atama, {"a": "m1", "b": "m1"})

    def test_eszamanli_degisiklikler_kaybolmaz(self):
        depo = DurumDeposu(self.y.durum)

        def ekle(n):
            for i in range(20):
                with depo.degistir() as d:
                    d.oncelik.append(f"{n}-{i}")

        isler = [threading.Thread(target=ekle, args=(n,)) for n in range(4)]
        for t in isler:
            t.start()
        for t in isler:
            t.join()
        self.assertEqual(len(depo.oku().oncelik), 80)

    def test_bitir_ortagi_da_temizler(self):
        depo = DurumDeposu(self.y.durum)
        with depo.degistir() as d:
            d.atama["a"] = "m1"
            d.ortak["a"] = ["m2"]
        with depo.degistir() as d:
            self.assertTrue(d.okuyabilir_mi("m2", "a"))
            d.bitir("a")
        self.assertEqual((depo.oku().atama, depo.oku().ortak), ({}, {}))


if __name__ == "__main__":
    unittest.main()
