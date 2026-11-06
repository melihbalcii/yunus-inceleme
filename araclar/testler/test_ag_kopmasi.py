"""Gerçek ağ arızasıyla kota güvenliği (yol haritası 2. adım; kalite/HATA-DEFTERI.md H-001).

Gerçek google-genai istemcisi ile sahte bir Gemini sunucusu arasına Toxiproxy girer ve bağlantıyı gerçekten keser,
geciktirir, yanıtı yarıda koparır. Sahte sunucu kendisine ULAŞAN istekleri sayar: kotayı harcayan budur. Denetlenen:
sunucuya ulaşan istek sayısı hiçbir arızada bütçeyi aşmaz ve `atilan` sayacı ile defter bunu doğru sayar.

Toxiproxy yoksa test atlanır. Sunucu yolu: TOXIPROXY_SERVER ortam değişkeni ya da <depo>/.cache/toxiproxy/.
"""
from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import numpy as np
from google import genai
from google.genai import types

from sesli import gemini as G


def _sunucu_yolu() -> str | None:
    if os.environ.get("TOXIPROXY_SERVER"):
        return os.environ["TOXIPROXY_SERVER"]
    adaylar = sorted((Path(__file__).resolve().parents[2] / ".cache" / "toxiproxy").glob("toxiproxy-server*"))
    return str(adaylar[0]) if adaylar else None


def _bos_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class SahteGemini(ThreadingHTTPServer):
    """generateContent'e 1 sn'lik ses döner; ulaşan istekleri sayar; istenirse yanıtı geciktirir."""

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Isleyici)
        self.daemon_threads = True
        self.ulasan = 0
        self.gecikme = 0.0
        self._kilit = threading.Lock()


class _Isleyici(BaseHTTPRequestHandler):
    server: SahteGemini

    def log_message(self, *a: object) -> None:
        pass

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        with self.server._kilit:
            self.server.ulasan += 1
        time.sleep(self.server.gecikme)
        pcm = (np.zeros(24000, dtype="<i2")).tobytes()
        govde = json.dumps({"candidates": [{"content": {"parts": [{"inlineData": {
            "mimeType": "audio/L16;codec=pcm;rate=24000", "data": base64.b64encode(pcm).decode()}}]},
            "finishReason": "STOP"}]}).encode()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(govde)))
            self.end_headers()
            self.wfile.write(govde)
        except OSError:
            pass  # bağlantıyı Toxiproxy kesti


@unittest.skipUnless(_sunucu_yolu(), "Toxiproxy kurulu değil")
class AgKopmasiTesti(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.api_port, cls.vekil_port = _bos_port(), _bos_port()
        # Bekçi kabuk: test süreci nasıl ölürse ölsün (mutasyon testinin zaman aşımı, kill -9) stdin kapanır,
        # `read` döner ve Toxiproxy kapatılır. Yoksa öldürülen her test bir Toxiproxy süreci bırakıyordu.
        cls.toxi = subprocess.Popen(
            ["/bin/sh", "-c", '"$0" -host 127.0.0.1 -port "$1" >/dev/null 2>&1 & p=$!; read _; kill $p',
             str(_sunucu_yolu()), str(cls.api_port)], stdin=subprocess.PIPE)
        cls.api = httpx.Client(base_url=f"http://127.0.0.1:{cls.api_port}", timeout=5)
        for _ in range(100):
            try:
                cls.api.get("/version")
                break
            except httpx.TransportError:
                time.sleep(0.05)
        cls.gemini = SahteGemini()
        threading.Thread(target=cls.gemini.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.gemini.shutdown()
        cls.api.close()
        assert cls.toxi.stdin is not None
        cls.toxi.stdin.close()
        cls.toxi.wait(5)

    def setUp(self) -> None:
        self.api.post("/reset")
        self.api.delete("/proxies/gemini")
        self.api.post("/proxies", json={"name": "gemini", "listen": f"127.0.0.1:{self.vekil_port}",
                                         "upstream": f"127.0.0.1:{self.gemini.server_address[1]}", "enabled": True})
        self.gemini.ulasan, self.gemini.gecikme = 0, 0.0

    def _zehir(self, tur: str, **ozellik: float) -> None:
        r = self.api.post("/proxies/gemini/toxics", json={"type": tur, "stream": "downstream", "attributes": ozellik})
        r.raise_for_status()

    def _tts(self, en_uzun: float = 3.0) -> tuple[G.GeminiTTS, list[dict[str, object]]]:
        defter: list[dict[str, object]] = []

        def kur() -> object:
            return genai.Client(api_key="deneme", http_options=types.HttpOptions(
                base_url=f"http://127.0.0.1:{self.vekil_port}", timeout=int((en_uzun + 5) * 1000)))
        return G.GeminiTTS(G.Arac("Deneme TTS", "deneme-model", "Fola"), "deneme", istek_suresi=0.5,
                           en_uzun_bekleme=en_uzun, bildir=lambda s: None, uyu=lambda s: None, istemci_kur=kur,
                           defter=defter.append), defter

    def _sonuclar(self, defter: list[dict[str, object]]) -> list[object]:
        return [k["sonuc"] for k in defter]

    def test_saglam_baglanti_tek_istek(self) -> None:
        t, defter = self._tts()
        self.assertEqual(len(t.uret("metin")), G.SR)
        self.assertEqual((self.gemini.ulasan, t.atilan), (1, 1))
        self.assertEqual(self._sonuclar(defter), ["ses"])

    def test_baglanti_reddedilirse_kota_harcanmaz(self) -> None:
        self.api.post("/proxies/gemini", json={"enabled": False})
        t, defter = self._tts()
        with self.assertRaises(G.GeciciHata):
            t.uret("metin")
        self.assertEqual((self.gemini.ulasan, t.atilan), (0, 0))
        self.assertEqual(self._sonuclar(defter), ["gitmedi"] * G.GITMEDI_DENEME)

    def test_istek_ulastiktan_sonra_kopma_butceyi_asmaz(self) -> None:
        """İstek Gemini'ye ulaştı (kota harcandı), yanıt gelmeden bağlantı koptu: en çok bütçe kadar istek."""
        self.gemini.gecikme = 0.3
        self._zehir("reset_peer", timeout=100)
        t, defter = self._tts()
        with self.assertRaises(G.GeciciHata):
            t.uret("metin", en_cok=2)
        self.assertLessEqual(self.gemini.ulasan, 2)
        self.assertEqual(t.atilan, self.gemini.ulasan, "ulaşan her istek kota harcamış sayılmalı")
        self.assertEqual(self._sonuclar(defter), ["kayip"] * self.gemini.ulasan)

    def test_baglanti_sessizce_koparsa_butce_icinde_bir_kez_yinelenir(self) -> None:
        """Toxiproxy veri geçirmeden bağlantıyı kapatıyor: istek ulaştı, yanıt yok. Bütçe 2: ilk istek + bir tekrar."""
        self._zehir("timeout", timeout=0)
        t, defter = self._tts()
        with self.assertRaises(G.GeciciHata):
            t.uret("metin", en_cok=2)
        self.assertEqual((self.gemini.ulasan, t.atilan), (2, 2))
        self.assertEqual(self._sonuclar(defter), ["kayip", "kayip"])

    def test_yanit_hic_gelmezse_ikinci_istek_atilmaz(self) -> None:
        self.gemini.gecikme = 8.0   # sunucu yanıtı tutuyor, bağlantı açık
        t, defter = self._tts(en_uzun=2.0)
        with self.assertRaises(G.GeciciHata):
            t.uret("metin", en_cok=2)
        self.assertEqual((self.gemini.ulasan, t.atilan), (1, 1))
        self.assertEqual(self._sonuclar(defter), ["zaman_asimi"])

    def test_yarida_kesilen_yanit_butceyi_asmaz(self) -> None:
        self._zehir("limit_data", bytes=200)
        t, _ = self._tts()
        with self.assertRaises(G.TTSHatasi):
            t.uret("metin", en_cok=2)
        self.assertLessEqual(self.gemini.ulasan, 2)
        self.assertEqual(t.atilan, self.gemini.ulasan)

    def test_geciken_yanit_beklenir_yeni_istek_atilmaz(self) -> None:
        self._zehir("latency", latency=1500)
        t, defter = self._tts(en_uzun=5.0)
        self.assertEqual(len(t.uret("metin")), G.SR)
        self.assertEqual((self.gemini.ulasan, t.atilan), (1, 1))
        self.assertEqual(self._sonuclar(defter), ["ses"])


if __name__ == "__main__":
    unittest.main()
