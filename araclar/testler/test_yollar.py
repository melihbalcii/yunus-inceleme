"""Yollar diskteki gerçek verilerle sözleşmedir: bir ad değişirse mevcut veri görünmez olur (ör. gemini-parcalar'daki
okunmuş bloklar yeniden okunur, kota boşa gider). Bu yüzden her yol tek tek sabitlenir."""
from __future__ import annotations

import unittest
from pathlib import Path

from sesli.yollar import PROJE_KOKU, Yollar


class YollarTesti(unittest.TestCase):
    def test_proje_ici_yollar(self):
        y = Yollar.kok_altinda(Path("/k"))
        beklenen = {
            "podcast": "/k/podcast", "eserler": "/k/podcast/eserler.json", "plan_csv": "/k/podcast/klasikler-100.csv",
            "tmp": "/k/.tmp", "parcalar": "/k/.tmp/gemini-parcalar", "durum": "/k/.tmp/fola-atama.json",
            "olcum": "/k/.tmp/fola-olcum.jsonl", "sinir": "/k/.tmp/fola-sinir.json",
            "gunluk": "/k/.tmp/fola-sirayla.log", "istek_defteri": "/k/.tmp/istek-defteri.jsonl",
            "zamanlayici_kilidi": "/k/.tmp/zamanlayici.kilit", "python": "/k/.venv-ses/bin/python",
            "gemini_env": "/k/.env", "kitaplik": "/k/kitaplik", "teslim": "/k/teslim", "emel_teslim": "/k/emel-teslim",
            "yayin": "/k/yayin", "cop": "/k/cop"}
        self.assertEqual({ad: str(getattr(y, ad)) for ad in beklenen}, beklenen)
        self.assertEqual(str(y.eser_kilidi("kisa-oyku")), "/k/.tmp/kilit/kisa-oyku.kilit")
        self.assertEqual(str(y.eser_klasoru("kisa-oyku")), "/k/podcast/kisa-oyku")
        self.assertEqual(str(y.fola_klasoru("kisa-oyku")), "/k/podcast/kisa-oyku/fola")

    def test_gercek_yollar(self):
        y, ev = Yollar.varsayilan(), Path.home()
        self.assertEqual(y.kok, PROJE_KOKU)
        from sesli import yollar
        self.assertEqual(PROJE_KOKU, Path(yollar.__file__).resolve().parents[2], "kök: araclar/'ın bir üstü")
        self.assertEqual(y.teslim, ev / "Desktop" / "sesli kitap fola")
        self.assertEqual(y.emel_teslim, ev / "Desktop" / "sesli kitap")
        self.assertEqual(y.yayin, ev / "Library" / "Caches" / "melihten-dinle" / "yayin", "yayın iCloud dışında")
        self.assertEqual(y.cop, ev / ".Trash", "silme yok: Çöp Sepeti")


if __name__ == "__main__":
    unittest.main()
