"""Ses sarmalayıcıları: Whisper'a doğru istek gider ve yanıtı doğru ayrıştırılır; ses kalitesi doğru örneklenir.
Modeller (Whisper, SQUIM) sahtedir; testler dakikalar süren model yüklemesi olmadan sarmalayıcı mantığını sınar."""
from __future__ import annotations

import sys
import types
import unittest
from unittest import mock

import numpy as np

from sesli import ses as S


class SahteWhisper:
    def __init__(self, sonuc):
        self.sonuc, self.cagrilar = sonuc, []

    def transcribe(self, ses, **ayar):
        self.cagrilar.append((len(ses), ayar))
        return self.sonuc

    def __enter__(self):
        self._yama = mock.patch.dict(sys.modules, {"mlx_whisper": types.SimpleNamespace(transcribe=self.transcribe)})
        self._yama.start()
        return self

    def __exit__(self, *a):
        self._yama.stop()


class WhisperTesti(unittest.TestCase):
    def test_dok_dogru_model_dil_ve_16khz_ses_gonderir(self):
        with SahteWhisper({"text": "  Kapı açıldı.  "}) as w:
            self.assertEqual(S.dok(np.zeros(S.SR * 3, dtype=np.float32), onceki_metne_bagli=True), "Kapı açıldı.")
        ((uzunluk, ayar),) = w.cagrilar
        self.assertEqual(uzunluk, 16000 * 3)
        self.assertEqual(ayar, {"path_or_hf_repo": S.WHISPER, "language": "tr", "condition_on_previous_text": True})

    def test_kelime_zamanlari_arindirilmis_kelimeler_ve_sureler(self):
        sonuc = {"segments": [{"words": [{"word": " Kapı,", "start": 0.0, "end": 0.4},
                                         {"word": " 4. Bölüm", "start": 0.5, "end": 1.25}]},
                              {"words": []}, {}]}
        with SahteWhisper(sonuc) as w:
            z = S.kelime_zamanlari(np.zeros(S.SR, dtype=np.float32))
        self.assertEqual(z, [("kapı", 0.0, 0.4), ("dördüncü", 0.5, 1.25), ("bölüm", 0.5, 1.25)])
        self.assertTrue(all(type(x) is float for _, a, b in z for x in (a, b)))
        ((_, ayar),) = w.cagrilar
        self.assertEqual((ayar["word_timestamps"], ayar["condition_on_previous_text"], ayar["language"]),
                         (True, False, "tr"))


class KaliteTesti(unittest.TestCase):
    def test_basi_ve_sonu_ayri_olculur(self):
        import torch
        verilen = iter(float(i) for i in range(1, 100))
        boylar = []

        def model(x):
            boylar.append(tuple(x.shape))
            return None, torch.tensor([next(verilen)])
        with mock.patch.object(S, "_squim", return_value=model):
            bas, son = S.kalite(np.zeros(S.SR * 95, dtype=np.float32))
        self.assertEqual(boylar, [(1, 16000 * 5)] * 3, "her 30 sn'den 5 sn'lik örnek")
        self.assertEqual((bas, son), (1.0, 3.0))
        verilen = iter([2.0] * 3 + [4.0] * 3 + [6.0] * 3)
        with mock.patch.object(S, "_squim", return_value=model):
            self.assertEqual(S.kalite(np.zeros(S.SR * 275, dtype=np.float32)), (2.0, 6.0), "üçte biri ortalaması")

    def test_kisa_ses_tek_ornek(self):
        import torch
        with mock.patch.object(S, "_squim", return_value=lambda x: (None, torch.tensor([3.3]))):
            bas, son = S.kalite(np.zeros(S.SR * 2, dtype=np.float32))
        self.assertAlmostEqual(bas, 3.3, places=5)
        self.assertAlmostEqual(son, 3.3, places=5)

    def test_bozulma_esikleri_sinirda(self):
        self.assertFalse(S.kalite_bozuk(3.6, S.KALITE_SINIR))
        self.assertTrue(S.kalite_bozuk(3.6, S.KALITE_SINIR - 0.01))
        self.assertFalse(S.kalite_bozuk(3.6, 3.6 - S.KALITE_DUSUS))
        self.assertTrue(S.kalite_bozuk(3.7, 3.6 - S.KALITE_DUSUS))


if __name__ == "__main__":
    unittest.main()
