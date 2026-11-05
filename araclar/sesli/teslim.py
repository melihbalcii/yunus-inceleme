"""Kontrolden geçen okumayı ~/Desktop/sesli kitap fola/<araç>/ klasörüne künyesiyle koyar.

Koşullar: eser etkin; fola/<eser>.mp3, kontrol.json (geçti), kalite.json (bozuk blok yok) ve motor.json var.
Aynı eserin başka araçla okunmuş eski hâli Çöp Sepeti'ne taşınır (silinmez).
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .katalog import Eser
from .kontrol import KontrolSonucu
from .yollar import Yollar
from mutagen.id3 import COMM, ID3, TALB, TCON, TIT2, TLAN, TPE1, TYER

YENILENECEK = {"Gemini 3.8 Live", "Gemini 2.5 Flash"}  # bu klasörlerdeki kayıtlar teslim sayılmaz (ses kalitesi)


class TeslimDurumu(StrEnum):
    KONULDU = "konuldu"
    GUNCEL = "zaten teslim edilmiş"
    KAYIT_YOK = "okuma kaydı yok"
    KONTROL_YOK = "kontrol sonucu yok"
    KONTROLDEN_GECMEDI = "kontrolden geçmedi"
    KALITE_DUSUK = "ses kalitesi denetiminden geçmedi"
    ARAC_BILINMIYOR = "hangi araçla okunduğu bilinmiyor"


@dataclass(frozen=True)
class TeslimSonucu:
    durum: TeslimDurumu
    hedef: Path | None = None
    eslesme: float | None = None
    cope: tuple[Path, ...] = ()


def gecerli_teslim(eser: Eser, yollar: Yollar) -> Path | None:
    """Eserin teslim klasöründeki geçerli TTS hâli (yenilenecek araç klasörleri dışında)."""
    return next((p for p in sorted(yollar.teslim.glob(f"*/{eser.dosya_adi}"))
                 if p.parent.name not in YENILENECEK), None)


def teslim_et(eser: Eser, yollar: Yollar) -> TeslimSonucu:
    fola = yollar.fola_klasoru(eser.ad)
    kaynak = fola / f"{eser.ad}.mp3"
    if not kaynak.exists():
        return TeslimSonucu(TeslimDurumu.KAYIT_YOK)
    mevcut = gecerli_teslim(eser, yollar)
    if mevcut and mevcut.stat().st_mtime >= kaynak.stat().st_mtime:
        return TeslimSonucu(TeslimDurumu.GUNCEL, mevcut)
    kontrol = KontrolSonucu.oku(fola)
    if kontrol is None:
        return TeslimSonucu(TeslimDurumu.KONTROL_YOK)
    if not kontrol.gecti:
        return TeslimSonucu(TeslimDurumu.KONTROLDEN_GECMEDI, eslesme=kontrol.eslesme)
    try:
        kalite = json.loads((fola / "kalite.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return TeslimSonucu(TeslimDurumu.KALITE_DUSUK, eslesme=kontrol.eslesme)
    if any(k["bozuk"] for k in kalite):
        return TeslimSonucu(TeslimDurumu.KALITE_DUSUK, eslesme=kontrol.eslesme)
    try:
        motor = json.loads((fola / "motor.json").read_text(encoding="utf-8"))
        arac_adi, ses_adi = motor["motor"], motor["ses"]
    except (OSError, ValueError, KeyError):
        return TeslimSonucu(TeslimDurumu.ARAC_BILINMIYOR)

    klasor = yollar.teslim / arac_adi.replace(" TTS", "")
    if klasor.name in YENILENECEK:
        return TeslimSonucu(TeslimDurumu.ARAC_BILINMIYOR)
    klasor.mkdir(parents=True, exist_ok=True)
    hedef = klasor / eser.dosya_adi
    gecici = klasor / f".{eser.dosya_adi}.yaziliyor"
    shutil.copy2(kaynak, gecici)
    kunye_yaz(gecici, eser, arac_adi, ses_adi)
    gecici.replace(hedef)

    cope = []
    for eski in yollar.teslim.glob(f"*/{eser.dosya_adi}"):
        if eski != hedef:
            cope.append(cope_tasi(eski, f"{eski.parent.name} - {eser.dosya_adi}", yollar))
    return TeslimSonucu(TeslimDurumu.KONULDU, hedef, kontrol.eslesme, tuple(cope))


def kunye_yaz(mp3: Path, eser: Eser, arac_adi: str, ses_adi: str) -> None:
    k = ID3()
    k.add(TIT2(encoding=3, text=eser.eser))
    k.add(TPE1(encoding=3, text=eser.yazar))
    k.add(TALB(encoding=3, text="Sesli Klasikler"))
    k.add(TCON(encoding=3, text="Sesli Kitap"))
    k.add(TLAN(encoding=3, text="tur"))
    k.add(TYER(encoding=3, text="2026"))
    k.add(COMM(encoding=3, lang="tur", desc="",
               text=f"Bu kayıt yapay zekâ sesiyle ({arac_adi}, {ses_adi}) seslendirilmiştir."))
    k.save(mp3)


def cope_tasi(dosya: Path, ad: str, yollar: Yollar) -> Path:
    """Dosyayı Çöp Sepeti'ne taşır; aynı adda dosya varsa sonuna sayı ekler (üzerine yazmaz)."""
    yollar.cop.mkdir(parents=True, exist_ok=True)
    hedef = yollar.cop / ad
    n = 2
    while hedef.exists():
        hedef = yollar.cop / f"{Path(ad).stem} ({n}){Path(ad).suffix}"
        n += 1
    shutil.move(str(dosya), str(hedef))
    return hedef
