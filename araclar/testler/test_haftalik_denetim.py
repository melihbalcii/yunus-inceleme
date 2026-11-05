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


if __name__ == "__main__":
    unittest.main()
