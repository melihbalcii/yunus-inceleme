"""Gemini istemcisi: gerçek istek atmadan, sahte istemciyle."""
from __future__ import annotations

import io
import threading
import time
import unittest
import wave
from types import SimpleNamespace

import numpy as np

from testler import yardim  # noqa: F401
from sesli import gemini as G


def _wav(saniye: float, hz: int = 24000) -> bytes:
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(hz)
        w.writeframes((np.ones(int(hz * saniye)) * 1000).astype("<i2").tobytes())
    return b.getvalue()


def _yanit(veri: bytes | None = None, mime: str = "audio/wav", sebep: str = "STOP"):
    parts = [SimpleNamespace(inline_data=SimpleNamespace(mime_type=mime, data=veri))] if veri is not None else []
    aday = SimpleNamespace(content=SimpleNamespace(parts=parts), finish_reason=sebep)
    return SimpleNamespace(candidates=[aday], prompt_feedback=None)


class SahteIstemci:
    def __init__(self, davranislar):
        self.davranislar = davranislar
        self.models = self

    def generate_content(self, **_):
        d = self.davranislar.pop(0)
        if isinstance(d, BaseException):
            raise d
        if callable(d):
            return d()
        return d


def _tts(davranislar, sure=5.0):
    paylasilan = list(davranislar)
    kurulum = []

    def kur():
        kurulum.append(1)
        return SahteIstemci(paylasilan)

    t = G.GeminiTTS(G.Arac("Deneme TTS", "deneme-model", "Fola"), "anahtar", istek_suresi=sure,
                    bildir=lambda s: None, uyu=lambda s: None, istemci_kur=kur)
    return t, kurulum


def _istemci_hatasi(kod: int, mesaj: str):
    from google.genai import errors
    return errors.ClientError(kod, {"error": {"code": kod, "message": mesaj, "status": "X"}})


class UretTesti(unittest.TestCase):
    def test_wav_yaniti(self):
        t, _ = _tts([_yanit(_wav(1.0))])
        ses = t.uret("merhaba")
        self.assertEqual(len(ses), 24000)
        self.assertAlmostEqual(float(ses[0]), 1000 / 32768, places=5)

    def test_l16_yaniti_ornekleme_hizi_donusur(self):
        ham = (np.ones(16000) * 100).astype("<i2").tobytes()
        t, _ = _tts([_yanit(ham, "audio/L16;rate=16000")])
        self.assertEqual(len(t.uret("x")), 24000)

    def test_gunluk_kota(self):
        t, _ = _tts([_istemci_hatasi(429, "Quota exceeded for metric: requests per day")])
        with self.assertRaises(G.KotaDoldu):
            t.uret("x")

    def test_dakikalik_sinir_beklenip_yinelenir(self):
        t, _ = _tts([_istemci_hatasi(429, "Please retry in 3s."), _yanit(_wav(0.1))])
        self.assertEqual(len(t.uret("x")), 2400)

    def test_kisa_metin_guvenlik_reddi_bolunemez(self):
        t, _ = _tts([_yanit(None, sebep="FinishReason.SAFETY")])
        with self.assertRaises(G.GuvenlikReddi) as h:
            t.uret("kısa")
        self.assertFalse(h.exception.bolunebilir)

    def test_uzun_metin_guvenlik_reddi_bolunebilir(self):
        t, _ = _tts([_yanit(None, sebep="PROHIBITED_CONTENT")])
        with self.assertRaises(G.GuvenlikReddi) as h:
            t.uret("x" * (G.GUVENLIK_BOLME + 1))
        self.assertTrue(h.exception.bolunebilir)

    def test_bos_yanit(self):
        t, _ = _tts([_yanit(None, sebep="OTHER")])
        with self.assertRaises(G.BosYanit):
            t.uret("x")

    def test_baglanilamazsa_yinelenir_sonra_gecici(self):
        import httpx
        t, kurulum = _tts([httpx.ConnectError("koptu")] * G.GITMEDI_DENEME)
        with self.assertRaises(G.GeciciHata):
            t.uret("x")
        self.assertEqual(len(kurulum), G.GITMEDI_DENEME)  # her denemede istemci yenilenir
        self.assertEqual(t.atilan, 0)  # istek gitmedi: kota harcanmadı

    def test_sunucu_hatasi_bir_kez_yinelenir(self):
        from google.genai import errors
        h = errors.ServerError(503, {"error": {"code": 503, "message": "meşgul", "status": "UNAVAILABLE"}})
        t, _ = _tts([h, _yanit(_wav(0.1))])
        self.assertEqual(len(t.uret("x")), 2400)
        self.assertEqual(t.atilan, 2)  # 503 kotayı harcamış olabilir: sayılır

    def test_istemin_bicimi(self):
        self.assertTrue(G.istem("metin").startswith("## Director's notes:\n"))
        self.assertTrue(G.istem("metin").endswith("## Transcript:\nmetin"))


if __name__ == "__main__":
    unittest.main()
