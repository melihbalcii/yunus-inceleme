"""Kayıt denetimi: okuma ortamında yalnız iCloud'da duran dosya (kalite/HATA-DEFTERI.md H-016)."""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import haftalik_denetim as H


class OrtamDenetimiTesti(unittest.TestCase):
    def setUp(self) -> None:
        self.kok = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.kok)
        for ad in (".venv-ses/lib", ".cache/python/bin", "araclar", "podcast"):
            (self.kok / ad).mkdir(parents=True)
        for yol in (".venv-ses/lib/torch.dylib", ".cache/python/bin/python3", "araclar/a.py", "podcast/kitap.mp3"):
            (self.kok / yol).write_bytes(b"x" * 10)

    def _icloudda(self, *adlar: str):
        def bayrak(yol: str) -> tuple[int, int]:
            return (H.SF_DATALESS if any(yol.endswith(a) for a in adlar) else 0), os.path.getsize(yol)
        return mock.patch.object(H, "_bayrak", bayrak)

    def test_hepsi_macteyse_alarm_yok(self) -> None:
        with self._icloudda():
            (b,) = H.ortami_denetle(self.kok)
        self.assertFalse(b.alarm)
        self.assertEqual(b.ayrinti, [])

    def test_okuma_ortamindaki_icloud_dosyasi_alarm_verir(self) -> None:
        with self._icloudda("torch.dylib", "python3"):
            (b,) = H.ortami_denetle(self.kok)
        self.assertTrue(b.alarm)
        self.assertIn("Mac'te olmayan dosya: 2", b.baslik)
        self.assertTrue(any(s.startswith(".venv-ses: 1 dosya") for s in b.ayrinti))
        self.assertTrue(any(s.startswith(".cache/python: 1 dosya") for s in b.ayrinti))

    def test_teslim_mp3_icloudda_olabilir(self) -> None:
        """Teslim edilmiş kitaplar iCloud'da durabilir: okuma programı onları açmaz."""
        with self._icloudda("kitap.mp3"):
            (b,) = H.ortami_denetle(self.kok)
        self.assertFalse(b.alarm)


class SurecVeTekrarTesti(unittest.TestCase):
    def test_caffeinate_ve_alt_surec_ikinci_kopya_sayilmaz(self):
        cikti = ("46707 .venv-ses/bin/python -u araclar/sesli_kitap.py oku\n"
                 "46709 caffeinate -is .venv-ses/bin/python -u araclar/sesli_kitap.py oku\n"
                 "46800 /k/.venv-ses/bin/python -u /k/araclar/sesli_kitap.py oku-eser x --model m\n")
        (b,) = H.surecleri_denetle(cikti)
        self.assertFalse(b.alarm)
        self.assertEqual(b.baslik, "Çalışan okuma programı kopyası: 1")

    def test_iki_zamanlayici_alarm(self):
        cikti = "1 python -u araclar/sesli_kitap.py oku\n2 python -u araclar/sesli_kitap.py oku\n"
        self.assertTrue(H.surecleri_denetle(cikti)[0].alarm)

    def test_kalite_icin_yeniden_okuma_olagan_fazlasi_alarm(self):
        import json
        def kayit(ozet, n):
            return [json.dumps({"zaman": "2026-11-06T03:30:00+0300", "ozet": ozet, "sonuc": "ses", "sn": 50})] * n
        bulgular = {b.baslik.split(":")[0]: b for b in H.defteri_denetle(kayit("a", 3) + kayit("b", 2) + kayit("c", 1))}
        self.assertFalse(bulgular[f"Aynı metin {H.EN_COK_DENEME} kereden fazla seslendirildi"].alarm)
        yeniden = bulgular[f"Kalite yüzünden yeniden okunan blok (en çok {H.EN_COK_DENEME} deneme, olağan)"]
        self.assertEqual(yeniden.ayrinti, ["a: 3 kez", "b: 2 kez"])
        fazla = {b.baslik.split(":")[0]: b for b in H.defteri_denetle(kayit("a", 4))}
        self.assertTrue(fazla[f"Aynı metin {H.EN_COK_DENEME} kereden fazla seslendirildi"].alarm)


if __name__ == "__main__":
    unittest.main()
