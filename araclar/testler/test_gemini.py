"""Gemini istemcisi: gerçek istek atmadan, sahte istemciyle."""
from __future__ import annotations

import io
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



class IstekIcerigiVeDefterTesti(unittest.TestCase):
    """Gemini'ye giden isteğin içeriği ve istek defteri. Defterdeki zaman ve özet, kayıt denetiminin "aynı metin iki kez
    okundu mu", "aynı anda iki istek var mı" sorularının dayanağıdır."""

    class KayitliIstemci:
        def __init__(self, yanitlar):
            self.yanitlar = list(yanitlar)
            self.models = self
            self.cagrilar: list[dict] = []

        def generate_content(self, **kw):
            self.cagrilar.append(kw)
            y = self.yanitlar.pop(0)
            if isinstance(y, BaseException):
                raise y
            return y() if callable(y) else y

    def _tts(self, yanitlar, **ayar):
        istemci = self.KayitliIstemci(yanitlar)
        self.defter: list[dict] = []
        self.mesajlar: list[str] = []
        saat = iter(float(x) for x in range(1_762_400_000, 1_762_500_000, 7))
        t = G.GeminiTTS(G.Arac("Deneme TTS", "deneme-model", "Fola"), "anahtar", bildir=self.mesajlar.append,
                        uyu=lambda s: None, istemci_kur=lambda: istemci, defter=self.defter.append,
                        **({"saat": lambda: next(saat)} | ayar))
        return t, istemci

    def test_istek_metni_modeli_ve_sesi_tasir(self):
        t, istemci = self._tts([_yanit(_wav(0.1))])
        t.uret("Kapı açıldı.")
        (c,) = istemci.cagrilar
        self.assertEqual(c["model"], "deneme-model")
        self.assertEqual(c["contents"], G.istem("Kapı açıldı."))
        self.assertIn("Kapı açıldı.", c["contents"])
        ayar = c["config"]
        self.assertEqual(ayar.speech_config.voice_config.prebuilt_voice_config.voice_name, "Fola")
        self.assertEqual(ayar.temperature, 1)
        self.assertEqual([str(m).lower().rsplit(".", 1)[-1] for m in ayar.response_modalities], ["audio"])

    def test_defter_kaydi_tam_ve_denetimin_okuyacagi_bicimde(self):
        import datetime as dt
        import hashlib
        t, _ = self._tts([_yanit(_wav(0.5))])
        t.uret("Kapı açıldı.")
        (k,) = self.defter
        zaman = dt.datetime.strptime(k["zaman"], "%Y-%m-%dT%H:%M:%S%z")
        self.assertEqual(zaman.timestamp(), 1_762_400_000)
        self.assertEqual({x: v for x, v in k.items() if x != "zaman"},
                         {"model": "deneme-model", "kr": 12, "sonuc": "ses", "sn": 7.0, "ses_sn": 0.5,
                          "ozet": hashlib.md5("Kapı açıldı.".encode()).hexdigest()[:12]})

    def test_basarisiz_istegin_kaydinda_ses_suresi_yok(self):
        from google.genai import errors
        t, _ = self._tts([errors.ServerError(503, {"error": {"code": 503, "message": "x", "status": "X"}}),
                          _yanit(_wav(0.1))])
        t.uret("metin")
        self.assertEqual([k["sonuc"] for k in self.defter], ["kayip", "ses"])
        self.assertNotIn("ses_sn", self.defter[0])

    def test_sayac_her_istekte_artar(self):
        t, _ = self._tts([_yanit(_wav(0.1)), _yanit(_wav(0.1)), _yanit(_wav(0.1))])
        for _ in range(3):
            t.uret("metin")
        self.assertEqual(t.atilan, 3)


class KotaSiniriTesti(unittest.TestCase):
    """429: günlük kota bittiyse hemen durulur; dakikalık sınırda Gemini'nin söylediği kadar (+2 sn) beklenir."""

    def _tts(self, davranislar):
        self.uykular: list[float] = []
        self.mesajlar: list[str] = []
        istemci = SahteIstemci(list(davranislar))
        return G.GeminiTTS(G.Arac("Deneme TTS", "deneme-model", "Fola"), "anahtar", bildir=self.mesajlar.append,
                           uyu=self.uykular.append, istemci_kur=lambda: istemci)

    def test_gunluk_kota_yazilislari(self):
        for mesaj in ("requests per day", "GenerateRequestsPerDayPerProject", "PER DAY limit", "perday"):
            with self.subTest(mesaj=mesaj), self.assertRaises(G.KotaDoldu) as h:
                self._tts([_istemci_hatasi(429, mesaj)]).uret("x")
            self.assertIn(mesaj, str(h.exception))
            self.assertEqual(self.uykular, [], "günlük kotada beklenmez")

    def test_soylenen_sure_kadar_beklenir_yoksa_artan_bekleme(self):
        t = self._tts([_istemci_hatasi(429, "Please retry in 3s."), _istemci_hatasi(429, "dakikalık sınır"),
                       _istemci_hatasi(429, "RETRY IN 7 seconds"), _yanit(_wav(0.1))])
        t.uret("x")
        self.assertEqual(self.uykular, [5, 60, 9])
        self.assertEqual(self.mesajlar[:3], ["dakikalık sınır: 5 sn bekleniyor", "dakikalık sınır: 60 sn bekleniyor",
                                             "dakikalık sınır: 9 sn bekleniyor"])
        self.assertEqual(t.atilan, 1, "429 kota harcamaz")

    def test_dakikalik_sinir_cok_tekrarlarsa_gecici_hata(self):
        t = self._tts([_istemci_hatasi(429, "retry in 1")] * G.DAKIKALIK_DENEME)
        with self.assertRaisesRegex(G.GeciciHata, "dakikalık sınır geçmedi"):
            t.uret("x")
        self.assertEqual(len(self.uykular), G.DAKIKALIK_DENEME - 1)

    def test_baska_istemci_hatasi_oldugu_gibi_iletilir(self):
        from google.genai import errors
        with self.assertRaises(errors.ClientError) as h:
            self._tts([_istemci_hatasi(400, "bad request per day")]).uret("x")
        self.assertEqual(h.exception.code, 400)


class DosyaDefteriTesti(unittest.TestCase):
    def test_her_kayit_bir_satir_turkce_harfler_korunur(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            yol = Path(d) / "defter.jsonl"
            yaz = G.dosya_defteri(yol)
            yaz({"sonuc": "ses", "not": "çağrı"})
            yaz({"sonuc": "kayip"})
            satirlar = yol.read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(x) for x in satirlar], [{"sonuc": "ses", "not": "çağrı"}, {"sonuc": "kayip"}])
        self.assertIn("çağrı", satirlar[0], "ensure_ascii=False: defter okunabilir kalsın")


if __name__ == "__main__":
    unittest.main()
