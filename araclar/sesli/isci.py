"""Tek eseri tek araçla okuyup kontrol eden alt süreç. Zamanlayıcı her eseri ayrı süreçte çalıştırır: Whisper ve
SQUIM modelleri iş bitince bellekten çıkar, bir çökme zamanlayıcıyı düşürmez. Sonuç çıkış koduyla bildirilir."""
from __future__ import annotations

import json
import subprocess
import traceback
from dataclasses import dataclass
from enum import IntEnum
from typing import Callable

from . import gemini as G
from .ayar import gerekli
from .hazirlik import metni_hazirla
from .katalog import Katalog
from .kilit import ZatenCalisiyor, tek_kopya
from .kontrol import kontrol_et
from .okuma import BolunemezHata, OkumaAyari, Okuyucu, Seslendirici
from .yollar import Yollar


class Cikis(IntEnum):
    TAMAM = 0
    HATA = 1          # beklenmeyen hata (ayrıntı günlükte)
    KOTA = 75         # aracın günlük kotası doldu; eser yarın aynı araçla sürer
    GUVENLIK = 76     # güvenlik filtresi kısa bir bloğu reddetti: bu araç bu eseri okuyamaz
    GECICI = 77       # bağlantı/sunucu sorunu sürdü: eser sorunlu değil, biraz sonra yeniden denenir
    BOLUNEMEZ = 78    # model tek paragraflık bloğa ses döndürmüyor: bu araç bu eseri okuyamaz

    @classmethod
    def koddan(cls, kod: int) -> "Cikis":
        try:
            return cls(kod)
        except ValueError:
            return cls.HATA


@dataclass(frozen=True)
class IsTanimi:
    ad: str
    arac_adi: str
    model: str
    ses: str
    ortak: tuple[str, ...]
    hedef_sn: int | None
    sabit_blok: int | None

    def arguman(self) -> list[str]:
        a = ["oku-eser", self.ad, "--arac-adi", self.arac_adi, "--model", self.model, "--ses", self.ses]
        if self.ortak:
            a += ["--ortak", ",".join(self.ortak)]
        if self.hedef_sn:
            a += ["--hedef-sn", str(self.hedef_sn)]
        elif self.sabit_blok:
            a += ["--sabit-blok", str(self.sabit_blok)]
        return a


def calistir(is_: IsTanimi, yollar: Yollar) -> Cikis:
    giris = yollar.kok / "araclar" / "sesli_kitap.py"
    r = subprocess.run([str(yollar.python), "-u", str(giris), *is_.arguman()])
    return Cikis.koddan(r.returncode)


def _gercek_tts(arac: G.Arac, yollar: Yollar, bildir: Callable[[str], None]) -> Seslendirici:
    return G.GeminiTTS(arac, gerekli(yollar.gemini_env, "GEMINI_API_KEY"), bildir=bildir,
                       defter=G.dosya_defteri(yollar.istek_defteri))


def _oku_ve_denetle(is_: IsTanimi, yollar: Yollar,
                    tts_kur: Callable[[G.Arac, Yollar, Callable[[str], None]], Seslendirici],
                    bildir: Callable[[str], None]) -> Cikis:
    eser = Katalog.yukle(yollar).al(is_.ad)
    metin = metni_hazirla(eser, yollar)
    fola = yollar.fola_klasoru(eser.ad)
    arac = G.Arac(is_.arac_adi, is_.model, is_.ses, is_.sabit_blok)
    tts = tts_kur(arac, yollar, bildir)
    ayar = OkumaAyari(model=is_.model, ses=is_.ses, ortak=is_.ortak, hedef_sn=is_.hedef_sn,
                      sabit_blok=is_.sabit_blok, siir=eser.siir)
    Okuyucu(tts, ayar, yollar, bildir=bildir).eseri_oku(metin, fola / f"{eser.ad}.mp3")
    (fola / "motor.json").write_text(json.dumps({"motor": arac.ad, "model": arac.model, "ses": arac.ses},
                                                ensure_ascii=False), encoding="utf-8")
    sonuc = kontrol_et(fola, yollar.parcalar, bildir=lambda s: None)
    bildir(f"kontrol: eşleşme %{sonuc.eslesme:.2f}, 0,90 altı {sonuc.dusuk}, atlama {len(sonuc.atlamalar)}"
           + ("" if sonuc.gecti else " — GEÇMEDİ"))
    return Cikis.TAMAM


def oku_eser(is_: IsTanimi, yollar: Yollar,
             tts_kur: Callable[[G.Arac, Yollar, Callable[[str], None]], Seslendirici] = _gercek_tts) -> Cikis:
    """Alt sürecin içinde çalışır: okur, kontrol eder; sonucu çıkış koduna çevirir."""

    def bildir(s: str) -> None:
        print(s, flush=True)

    try:
        with tek_kopya(yollar.eser_kilidi(is_.ad)):  # aynı eseri iki süreç aynı anda okumasın
            return _oku_ve_denetle(is_, yollar, tts_kur, bildir)
    except ZatenCalisiyor as h:
        bildir(f"GEÇİCİ SORUN: {is_.ad} şu an başka bir süreçte okunuyor; {h}")
        return Cikis.GECICI
    except G.KotaDoldu:
        bildir("KOTA_DOLDU: günlük ücretsiz kota bitti; yarın kaldığı yerden sürer.")
        return Cikis.KOTA
    except G.GuvenlikReddi:
        bildir("GUVENLIK: güvenlik filtresi bu metni reddetti; bu araçla okunamaz.")
        return Cikis.GUVENLIK
    except BolunemezHata as h:
        bildir(f"BOŞ YANIT: {h}")
        return Cikis.BOLUNEMEZ
    except G.GeciciHata as h:
        bildir(f"GEÇİCİ SORUN: {h}")
        return Cikis.GECICI
    except Exception:  # noqa: BLE001 — süreç sınırı: ayrıntı günlüğe, zamanlayıcıya yalnız kod
        bildir(traceback.format_exc())
        return Cikis.HATA
