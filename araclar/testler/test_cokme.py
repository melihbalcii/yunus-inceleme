"""Çökme testi (yol haritası 2. adım; kalite/HATA-DEFTERI.md H-002).

Okuma programı gerçek bir süreçte, en kötü anlarda öldürülür (os._exit: elektrik kesilmesi, kill -9, Mac'in
yeniden başlaması gibi) ve yeniden başlatılır. Denetlenen: kaç kez çökerse çöksün bir bloğa günlük tavandan fazla
istek atılmaz; Gemini'den gelmiş bir ses yeniden istenmez; yarım dosya kitaba girmez.
"""
from __future__ import annotations

import os
import subprocess
import sys

from sesli.okuma import BLOK_TAVANI, blok_dosyasi, OkumaAyari
from testler.yardim import ARACLAR, GeciciKokTesti

METIN = "Birinci paragraf, kısa bir cümle.\n\nİkinci paragraf, o da kısa."


class CokmeTesti(GeciciKokTesti):
    def setUp(self) -> None:
        super().setUp()
        self.metin = self.kok / "blok.txt"
        self.metin.write_text(METIN, encoding="utf-8")

    def _calistir(self, cokme: str = "") -> int:
        ortam = {**os.environ, "COKME": cokme}
        r = subprocess.run([sys.executable, "-m", "testler.cokme_iscisi", str(self.kok), str(self.metin)],
                           cwd=ARACLAR, env=ortam, capture_output=True, text=True, timeout=120, check=False)
        if r.returncode not in (0, 3, 9):
            self.fail(f"işçi beklenmedik biçimde düştü ({r.returncode}):\n{r.stderr[-2000:]}")
        return r.returncode

    def _istek(self) -> int:
        d = self.kok / "istekler.log"
        return len(d.read_text().splitlines()) if d.exists() else 0

    def _blok(self):
        return blok_dosyasi(self.y.parcalar, METIN, OkumaAyari(model="deneme-model", ses="Fola"))

    def test_cokmeden_okuma_tek_istek(self) -> None:
        self.assertEqual(self._calistir(), 0)
        self.assertEqual(self._istek(), 1)
        self.assertTrue(self._blok().exists())

    def test_istek_sirasinda_tekrar_tekrar_cokse_de_gunluk_tavan_asilmaz(self) -> None:
        """Her başlatmada istek gidiyor ve yanıt gelmeden süreç ölüyor. Sayaç istekten sonra yazılırsa hiç artmaz
        ve her yeniden başlatma yeni bir kota harcar."""
        for _ in range(BLOK_TAVANI + 3):
            if self._calistir("istek") == 3:
                break
        self.assertLessEqual(self._istek(), BLOK_TAVANI)
        self.assertEqual(self._calistir("istek"), 3, "tavan dolunca yeni istek atılmamalı")
        self.assertLessEqual(self._istek(), BLOK_TAVANI)

    def test_olcum_sirasinda_coken_okumanin_sesi_yeniden_istenmez(self) -> None:
        """Ses geldi, Whisper ölçümü sürerken (dakikalar) süreç öldü: gelen ses kaybolmamalı."""
        self.assertEqual(self._calistir("olcum"), 9)
        self.assertEqual(self._istek(), 1)
        self.assertEqual(self._calistir(), 0)
        self.assertEqual(self._istek(), 1, "gelmiş ses yeniden istendi: kota boşa gitti")
        self.assertTrue(self._blok().exists())

    def test_yarim_kalan_dosya_kitaba_girmez(self) -> None:
        self.assertEqual(self._calistir("olcum"), 9)
        self.assertEqual(self._calistir(), 0)
        kalinti = [p.name for p in self.y.parcalar.iterdir() if "yaziliyor" in p.name or "deneme" in p.name]
        self.assertEqual(kalinti, [], "blok bitince deneme ya da yarım dosya kalmamalı")
