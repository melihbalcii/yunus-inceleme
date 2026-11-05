"""Gemini TTS istemcisi: bir metni tek istekte sese çevirir.

Hatalar istisna olarak bildirilir (eskiden kütüphane içinden sys.exit ile süreç kapatılıyordu):
  KotaDoldu      günlük ücretsiz kota bitti: bu araç bugün başka istek atmaz
  GuvenlikReddi  güvenlik filtresi reddetti; `bolunebilir` ise metin uzun, yarısı geçebilir (3.1 uzunluğa takılıyor)
  BosYanit       model ses döndürmedi: aynı metni yinelemek kotayı yer, çağıran metni böler
  GeciciHata     bağlantı/sunucu sorunu yinelemelere rağmen sürdü: eser sorunlu değildir, sonra yeniden denenir

Asılı istek koruması: httpx'in süre sınırı tekil okumalara bakar ve Mac uyuyunca işlemez (4 Kasım'da istek 6 saat
askıda kaldı). Her istek ayrı bir iş parçacığında çalışır; çağıran duvar saatine (time.time) bakarak bekler, süre
dolunca isteği bırakır, istemciyi yeniler ve yeniden dener.
"""
from __future__ import annotations

import io
import re
import threading
import time
import wave
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

import numpy as np

from .ses import SR, Dalga, yeniden_ornekle

T = TypeVar("T")

USLUP = ("Deneyimli bir Türk sesli kitap anlatıcısı. Sıcak, samimi, duygulu ve sakin; acele etmeden, "
         "anlama göre vurgu yaparak ve düşünceli yerlerde kısa duraklamalarla okur.")
# bundan kısa metin güvenlikte reddedilirse eser bu araçla okunamaz; uzunsa ikiye bölünüp yeniden denenir
# (3.1: Gazâlî'nin 3454 kr'lik bloğu reddedildi, yarıları 1204 ve 2248 kr okundu)
GUVENLIK_BOLME = 1000
ISTEK_SURESI = 15 * 60   # sn; 19 dakikalık ses 3-6 dk'da gelir
BAGLANTI_DENEME = 3
SUNUCU_DENEME = 3
DAKIKALIK_DENEME = 8


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


class _ZamanAsimi(Exception):
    pass


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


def _sureli(is_: Callable[[], T], sure: float) -> T:
    """is_()'i ayrı iş parçacığında çalıştırır; duvar saatiyle `sure` saniye içinde bitmezse _ZamanAsimi."""
    deger: list[T] = []
    hata: list[BaseException] = []

    def calis() -> None:
        try:
            deger.append(is_())
        except BaseException as h:  # noqa: BLE001 — çağıran iş parçacığına aynen taşınır
            hata.append(h)

    t = threading.Thread(target=calis, daemon=True, name="gemini-istek")
    t.start()
    bitis = time.time() + sure
    while t.is_alive():
        if time.time() >= bitis:
            raise _ZamanAsimi(f"{sure:.0f} sn içinde yanıt gelmedi")
        t.join(timeout=min(5.0, max(0.0, bitis - time.time())))
    if hata:
        raise hata[0]
    return deger[0]


class GeminiTTS:
    def __init__(self, arac: Arac, anahtar: str, *, istek_suresi: float = ISTEK_SURESI,
                 bildir: Callable[[str], None] = print, uyu: Callable[[float], None] = time.sleep,
                 istemci_kur: Callable[[], Any] | None = None) -> None:
        self.arac = arac
        self._anahtar = anahtar
        self._istek_suresi = istek_suresi
        self._bildir = bildir
        self._uyu = uyu
        self._istemci_kur = istemci_kur or self._varsayilan_istemci
        self._istemci = self._istemci_kur()

    def _varsayilan_istemci(self) -> Any:  # google.genai.Client
        from google import genai
        from google.genai import types
        # httpx süresi yedek koruma; asıl sınır _sureli'deki duvar saati
        return genai.Client(api_key=self._anahtar,
                            http_options=types.HttpOptions(timeout=int((self._istek_suresi + 60) * 1000)))

    def _ayar(self) -> Any:  # google.genai.types.GenerateContentConfig
        from google.genai import types
        return types.GenerateContentConfig(
            temperature=1, response_modalities=["audio"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.arac.ses))))

    def uret(self, metin: str) -> Dalga:
        """Metni seslendirir. Dakikalık sınırda bekler; günlük kota, güvenlik, boş yanıt ve kalıcı bağlantı sorunu
        modül başındaki istisnalarla bildirilir."""
        import httpx
        from google.genai import errors

        baglanti = sunucu = dakikalik = 0
        while True:
            try:
                yanit = _sureli(lambda: self._istemci.models.generate_content(
                    model=self.arac.model, contents=istem(metin), config=self._ayar()), self._istek_suresi)
                return self._yanittan_ses(yanit, metin)
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
            except (_ZamanAsimi, httpx.TimeoutException, httpx.TransportError, ConnectionError) as h:
                baglanti += 1
                if baglanti >= BAGLANTI_DENEME:
                    raise GeciciHata(f"bağlantı sorunu sürüyor: {h!r}") from h
                self._bildir(f"bağlantı koptu ya da zaman aşımı, tekrar: {h!r}")
                self._istemci = self._istemci_kur()  # asılı bağlantı havuzunu bırak
                self._uyu(30)
            except errors.ServerError as h:
                sunucu += 1
                if sunucu >= SUNUCU_DENEME:
                    raise GeciciHata(f"sunucu hatası sürüyor: {h.code}") from h
                self._bildir(f"sunucu hatası, tekrar: {h.code}")
                self._uyu(15 * sunucu)

    def _yanittan_ses(self, yanit: Any, metin: str) -> Dalga:
        aday = yanit.candidates[0] if getattr(yanit, "candidates", None) else None
        parca = aday.content.parts[0].inline_data if (aday and aday.content and aday.content.parts) else None
        if parca is None:
            sebep = getattr(aday, "finish_reason", None)
            geri = getattr(yanit, "prompt_feedback", None)
            self._bildir(f"boş yanıt: bitiş sebebi {sebep}, istem geri bildirimi {geri}")
            if "SAFETY" in str(sebep) or "PROHIBITED" in str(sebep):
                raise GuvenlikReddi(len(metin))
            raise BosYanit(str(sebep))
        return _pcm_coz(parca.mime_type, parca.data)
