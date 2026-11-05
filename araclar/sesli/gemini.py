"""Gemini TTS istemcisi: bir metni tek istekte sese çevirir.

Hatalar istisna olarak bildirilir:
  KotaDoldu      günlük ücretsiz kota bitti: bu araç bugün başka istek atmaz
  GuvenlikReddi  güvenlik filtresi reddetti; `bolunebilir` ise metin uzun, yarısı geçebilir (3.1 uzunluğa takılıyor)
  BosYanit       model ses döndürmedi: aynı metni yinelemek kotayı yer, çağıran metni böler
  GeciciHata     bağlantı/sunucu sorunu sürdü ya da istek bütçesi bitti: eser sorunlu değildir, sonra yeniden denenir

Kota güvenliği (5 Kasım, Yunus'un incelemesi: hata durumlarında aynı iş arka planda 2-4 kez yaptırılıyordu):
- Bir anda en çok BİR istek. Önceki istek hâlâ sürüyorsa yenisi atılmaz (GeciciHata). Eskiden süre dolunca istek
  bırakılıp hemen yenisi atılıyordu; bırakılan istek Gemini'de sürüp kotayı yiyordu.
- Süre dolunca istek bırakılmaz, aynı isteğin yanıtı beklenir (geç gelen ses kullanılır). Yalnız EN_UZUN_BEKLEME
  aşılırsa vazgeçilir; yeni istek atılmaz, GeciciHata verilir. Alt süreç kapanınca bağlantı da kapanır.
- Hatalar ikiye ayrılır: "istek hiç gitmedi" (bağlanılamadı) güvenle yinelenir; "gitti ama yanıt kayboldu"
  (okuma zaman aşımı, bağlantı yanıtsız kapandı, sunucu hatası) kotayı harcamış olabilir, yalnız bütçe izin verirse
  yinelenir. `uret(metin, en_cok=n)`: bu çağrıda kotayı harcayabilecek en çok n istek.
- Bekleme duvar saatine (time.time) bakar: Mac uyuyunca süre sayaçları durur (4 Kasım'da istek 6 saat askıda kaldı).
- Atılan her istek `defter`e yazılır (.tmp/istek-defteri.jsonl): boşa giden istek tahmin edilmez, ölçülür.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar
from collections.abc import Callable

import numpy as np

from .ses import SR, Dalga, yeniden_ornekle

T = TypeVar("T")

USLUP = ("Deneyimli bir Türk sesli kitap anlatıcısı. Sıcak, samimi, duygulu ve sakin; acele etmeden, "
         "anlama göre vurgu yaparak ve düşünceli yerlerde kısa duraklamalarla okur.")
# bundan kısa metin güvenlikte reddedilirse eser bu araçla okunamaz; uzunsa ikiye bölünüp yeniden denenir
# (3.1: Gazâlî'nin 3454 kr'lik bloğu reddedildi, yarıları 1204 ve 2248 kr okundu)
GUVENLIK_BOLME = 1000
ISTEK_SURESI = 15 * 60       # sn; 19 dakikalık ses 3-6 dk'da gelir: bu süre aşılınca günlüğe uyarı yazılır
EN_UZUN_BEKLEME = 45 * 60    # sn; aynı isteğin yanıtı en çok bu kadar beklenir
GITMEDI_DENEME = 3           # bağlanılamayan istek (kota harcanmaz) en çok bu kadar denenir
DAKIKALIK_DENEME = 8         # dakikalık sınır (429, istek reddedilir, kota harcanmaz)
VARSAYILAN_BUTCE = 2         # kotayı harcayabilecek istek: ilk istek + yanıtı kaybolursa bir tekrar


class TTSHatasi(Exception):
    pass


class KotaDoldu(TTSHatasi):
    pass


class GuvenlikReddi(TTSHatasi):
    def __init__(self, uzunluk: int):
        super().__init__(f"güvenlik filtresi reddetti ({uzunluk} kr)")
        self.bolunebilir = uzunluk > GUVENLIK_BOLME


class BosYanit(TTSHatasi):
    pass


class GeciciHata(TTSHatasi):
    pass


class _Gitmedi(Exception):
    """İstek Gemini'ye ulaşmadı: kota harcanmadı, güvenle yinelenir."""


class _Kayip(Exception):
    """İstek gitti ama yanıt alınamadı: kota harcanmış olabilir."""


Defter = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class Arac:
    ad: str               # "Gemini 3.8 Flash Lite TTS": teslim alt klasörü ve künye bu addan
    model: str
    ses: str
    sabit_blok: int | None = None  # None: uyarlamalı plan; sayı: bu sınırla sabit bloklar (3.1)

    @property
    def klasor_adi(self) -> str:
        return self.ad.replace(" TTS", "")


def istem(metin: str) -> str:
    return f"## Director's notes:\n{USLUP}\n\n## Transcript:\n{metin}"


def _pcm_coz(mime: str, veri: bytes) -> Dalga:
    if mime.startswith("audio/wav"):
        with wave.open(io.BytesIO(veri)) as w:
            hz, ham = w.getframerate(), w.readframes(w.getnframes())
    else:  # audio/L16;rate=24000
        m = re.search(r"rate=(\d+)", mime)
        if not m:
            raise BosYanit(f"tanınmayan ses biçimi: {mime}")
        hz, ham = int(m.group(1)), veri
    ses = np.frombuffer(ham, dtype="<i2").astype(np.float32) / 32768
    return yeniden_ornekle(ses, hz, SR)


class GeminiTTS:
    def __init__(self, arac: Arac, anahtar: str, *, istek_suresi: float = ISTEK_SURESI,
                 en_uzun_bekleme: float = EN_UZUN_BEKLEME, bildir: Callable[[str], None] = print,
                 uyu: Callable[[float], None] = time.sleep, saat: Callable[[], float] = time.time,
                 istemci_kur: Callable[[], Any] | None = None, defter: Defter | None = None) -> None:
        self.arac = arac
        self._anahtar = anahtar
        self._istek_suresi = istek_suresi
        self._en_uzun = en_uzun_bekleme
        self._bildir = bildir
        self._uyu = uyu
        self._saat = saat
        self._defter = defter or (lambda kayit: None)
        self._istemci_kur = istemci_kur or self._varsayilan_istemci
        self._istemci = self._istemci_kur()
        self._ucusta: threading.Thread | None = None
        self.atilan = 0
        """Kotayı harcamış olabilecek istek sayısı (ses gelen, boş/ret dönen ve yanıtı kaybolanlar)."""

    def _varsayilan_istemci(self) -> Any:  # google.genai.Client
        from google import genai
        from google.genai import types
        # httpx süresi yedek koruma: asılı istek en geç EN_UZUN_BEKLEME + 1 dk'da düşer
        return genai.Client(api_key=self._anahtar,
                            http_options=types.HttpOptions(timeout=int((self._en_uzun + 60) * 1000)))

    def _ayar(self) -> Any:  # google.genai.types.GenerateContentConfig
        from google.genai import types
        return types.GenerateContentConfig(
            temperature=1, response_modalities=["audio"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.arac.ses))))

    def uret(self, metin: str, en_cok: int = VARSAYILAN_BUTCE) -> Dalga:
        """Metni seslendirir; bu çağrıda kotayı harcayabilecek en çok `en_cok` istek atar. Dakikalık sınırda
        bekler; günlük kota, güvenlik, boş yanıt ve sürüp giden bağlantı sorunu modül başındaki istisnalarla
        bildirilir."""
        from google.genai import errors

        if en_cok < 1:
            raise GeciciHata("istek bütçesi bitti")
        gitmedi = dakikalik = harcanan = 0
        while True:
            try:
                yanit, bas = self._istek(metin)
            except _Gitmedi as h:
                gitmedi += 1
                if gitmedi >= GITMEDI_DENEME:
                    raise GeciciHata(f"Gemini'ye bağlanılamıyor: {h.__cause__!r}") from h
                self._bildir(f"bağlanılamadı (kota harcanmadı), tekrar: {h.__cause__!r}")
                self._istemci = self._istemci_kur()
                self._uyu(30)
                continue
            except _Kayip as h:
                harcanan += 1
                if harcanan >= en_cok:
                    raise GeciciHata(f"yanıt alınamadı, {harcanan} istek harcandı; yeni istek atılmıyor: "
                                     f"{h.__cause__!r}") from h
                self._bildir(f"yanıt kayboldu (kota harcanmış olabilir), bir kez daha: {h.__cause__!r}")
                self._istemci = self._istemci_kur()
                self._uyu(30)
                continue
            except errors.ClientError as h:
                if h.code != 429:
                    raise
                if re.search(r"per ?day|PerDay", str(h), re.I):
                    raise KotaDoldu(str(h)[:200]) from h
                dakikalik += 1
                if dakikalik >= DAKIKALIK_DENEME:
                    raise GeciciHata("dakikalık sınır geçmedi") from h
                m = re.search(r"retry in (\d+)", str(h), re.I)
                sn = int(m.group(1)) + 2 if m else 30 * dakikalik
                self._bildir(f"dakikalık sınır: {sn} sn bekleniyor")
                self._uyu(sn)
                continue
            return self._yanittan_ses(yanit, metin, bas)

    def _istek(self, metin: str) -> tuple[Any, float]:
        """Tek istek atar ve yanıtını bekler. Önceki istek sürüyorsa yenisini atmaz. Hata türünü _Gitmedi /
        _Kayip / Gemini'nin kendi istisnalarına çevirir; her isteği deftere yazar."""
        import httpx
        from google.genai import errors

        if self._ucusta is not None and self._ucusta.is_alive():
            raise GeciciHata("önceki istek hâlâ sürüyor; aynı anda ikinci istek atılmaz")
        sonuc: list[Any] = []
        hata: list[BaseException] = []
        istemci = self._istemci

        def calis() -> None:
            try:
                sonuc.append(istemci.models.generate_content(
                    model=self.arac.model, contents=istem(metin), config=self._ayar()))
            except BaseException as h:  # noqa: BLE001 — çağıran iş parçacığına aynen taşınır
                hata.append(h)

        bas = self._saat()
        t = threading.Thread(target=calis, daemon=True, name="gemini-istek")
        self._ucusta = t
        t.start()
        uyari = bas + self._istek_suresi
        while t.is_alive():
            simdi = self._saat()
            if simdi - bas >= self._en_uzun:
                self._yaz(metin, bas, "zaman_asimi")
                self.atilan += 1
                raise GeciciHata(f"istek {self._en_uzun / 60:.0f} dk'da yanıt vermedi; yeni istek atılmıyor")
            if simdi >= uyari:
                self._bildir(f"yanıt gecikiyor ({(simdi - bas) / 60:.0f} dk); aynı isteğin yanıtı bekleniyor")
                uyari += self._istek_suresi
            t.join(timeout=min(5.0, max(0.01, bas + self._en_uzun - simdi)))
        if not hata:
            self.atilan += 1
            return sonuc[0], bas
        h = hata[0]
        if isinstance(h, (httpx.ConnectError, httpx.ConnectTimeout, ConnectionRefusedError)):
            self._yaz(metin, bas, "gitmedi")
            raise _Gitmedi() from h
        if isinstance(h, (httpx.TimeoutException, httpx.TransportError, ConnectionError, errors.ServerError)):
            self._yaz(metin, bas, "kayip")
            self.atilan += 1
            raise _Kayip() from h
        if isinstance(h, errors.ClientError) and h.code == 429:
            self._yaz(metin, bas, "sinir")
        else:
            self._yaz(metin, bas, "hata")
            self.atilan += 1
        raise h

    def _yaz(self, metin: str, bas: float, sonuc: str, ses_sn: float | None = None) -> None:
        kayit: dict[str, Any] = {
            "zaman": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(bas)), "model": self.arac.model,
            "kr": len(metin), "ozet": hashlib.md5(metin.encode(), usedforsecurity=False).hexdigest()[:12], "sonuc": sonuc,
            "sn": round(self._saat() - bas, 1)}
        if ses_sn is not None:
            kayit["ses_sn"] = round(ses_sn, 1)
        try:
            self._defter(kayit)
        except OSError:
            pass  # defter yazılamadı diye okuma durmasın

    def _yanittan_ses(self, yanit: Any, metin: str, bas: float) -> Dalga:
        aday = yanit.candidates[0] if getattr(yanit, "candidates", None) else None
        parca = aday.content.parts[0].inline_data if (aday and aday.content and aday.content.parts) else None
        if parca is None:
            sebep = getattr(aday, "finish_reason", None)
            geri = getattr(yanit, "prompt_feedback", None)
            self._bildir(f"boş yanıt: bitiş sebebi {sebep}, istem geri bildirimi {geri}")
            if "SAFETY" in str(sebep) or "PROHIBITED" in str(sebep):
                self._yaz(metin, bas, "guvenlik")
                raise GuvenlikReddi(len(metin))
            self._yaz(metin, bas, "bos")
            raise BosYanit(str(sebep))
        ses = _pcm_coz(parca.mime_type, parca.data)
        self._yaz(metin, bas, "ses", ses_sn=len(ses) / SR)
        return ses


def dosya_defteri(yol: Path) -> Defter:
    """İstek defterine satır ekleyen işlev (.tmp/istek-defteri.jsonl)."""
    def yaz(kayit: dict[str, Any]) -> None:
        with open(yol, "a", encoding="utf-8") as f:
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
    return yaz
