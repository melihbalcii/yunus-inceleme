"""Okuma kuyruğu ve okuma metni.

Kuyruk: etkin olup geçerli TTS hâli henüz teslim edilmemiş (ya da teslimden sonra yeniden okunmuş) eserler, kısadan
uzuna. Okuma metni podcast/<eser>/fola/seslendirme-metni.txt'dir; tek parça eserde podcast/<eser>/seslendirme-metni.txt,
parça parça (kisim-N, bolum-NN, boy-NN) hazırlanmış eserde parçaların metni birleştirilir: parça duyuruları ve ara
kapanışlar çıkar, eserin kendi bölüm başlıkları kalır.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .katalog import Eser, Katalog
from .teslim import gecerli_teslim
from .yollar import Yollar

BIRIM = re.compile(r"(bolum|kisim|boy)-(\d+)$")
SIRA_BASLIK = re.compile(r"^[A-ZÇĞİÖŞÜ][a-zçğıöşü]+( [a-zçğıöşü]+)? bölüm\.$")


class MetinHatasi(ValueError):
    pass


@dataclass(frozen=True)
class KuyrukIsi:
    eser: Eser
    uzunluk: int        # okuma metninin karakter sayısı
    metin_dosyasi: Path

    @property
    def ad(self) -> str:
        return self.eser.ad


def _birim_no(klasor: Path) -> tuple[str, int]:
    """Parça klasörünün (tür, sıra) bilgisi: ("bolum", 3) gibi; parça klasörü değilse MetinHatasi."""
    m = BIRIM.match(klasor.name)
    if m is None:
        raise MetinHatasi(f"{klasor}: parça klasörü değil")
    return m[1], int(m[2])


def birimler(klasor: Path) -> list[Path]:
    if not klasor.is_dir():
        return []
    return sorted((p for p in klasor.iterdir() if p.is_dir() and BIRIM.match(p.name)), key=lambda p: _birim_no(p)[1])


def _paragraflar(dosya: Path) -> list[str]:
    return [p.strip() for p in dosya.read_text(encoding="utf-8").split("\n\n") if p.strip()]


def birlesik_paragraflar(klasor: Path) -> list[str]:
    bs = birimler(klasor)
    tur = _birim_no(bs[0])[0]
    sonuc: list[str] = []
    for n, b in enumerate(bs):
        ps = _paragraflar(b / "seslendirme-metni.txt")
        son = n == len(bs) - 1
        if tur == "boy":
            if n > 0:
                ps[0] = ps[0].split(". ", 1)[1]  # "Dede Korkut Hikâyeleri. Birinci boy: …" → "Birinci boy: …"
            if "dinlediniz" not in ps[-1]:
                raise MetinHatasi(f"{b}: kapanış bulunamadı")
            if not son:
                ps = ps[:-1]
        else:
            if n == 0:
                ps[0] = re.sub(r" (Birinci|İlk) (kısım|bölüm)\.$", "", ps[0])
            else:
                ps = ps[1:]
            if tur == "bolum" and len(ps) > 1 and SIRA_BASLIK.match(ps[0 if n else 1]):
                del ps[0 if n else 1]
            if not son:
                if not re.search(r"(kısmın|bölümün) sonu\.", ps[-1]):
                    raise MetinHatasi(f"{b}: geçiş duyurusu yok: {ps[-1][:80]}")
                ps = ps[:-1]
        sonuc += ps
    # tek dosyada "…nın birinci bölümünü dinlediniz" → "…nı dinlediniz" (eserin tamamı)
    sonuc[-1] = re.sub(r"(\S+)n (?:on |yirmi )?\S+ (boyunu|bölümünü) dinlediniz\.", r"\1 dinlediniz.", sonuc[-1])
    return sonuc


def okuma_metni(eser: Eser, yollar: Yollar) -> str:
    klasor = yollar.eser_klasoru(eser.ad)
    try:
        ps = birlesik_paragraflar(klasor) if birimler(klasor) else _paragraflar(klasor / "seslendirme-metni.txt")
    except OSError as h:
        raise MetinHatasi(f"{eser.ad}: okuma metni okunamadı ({h.strerror}: {h.filename})") from h
    if not ps:
        raise MetinHatasi(f"{eser.ad}: okuma metni boş")
    return "\n\n".join(ps) + "\n"


def metni_hazirla(eser: Eser, yollar: Yollar) -> Path:
    """fola/seslendirme-metni.txt'yi kaynağa göre günceller (değişmediyse dokunmaz) ve yolunu döndürür."""
    hedef = yollar.fola_klasoru(eser.ad) / "seslendirme-metni.txt"
    yazi = okuma_metni(eser, yollar)
    if not hedef.exists() or hedef.read_text(encoding="utf-8") != yazi:
        hedef.parent.mkdir(parents=True, exist_ok=True)
        gecici = hedef.with_name(hedef.name + ".yaziliyor")
        gecici.write_text(yazi, encoding="utf-8")
        gecici.replace(hedef)
    return hedef


def okunacak_mi(eser: Eser, yollar: Yollar) -> bool:
    if not eser.etkin:
        return False
    if not eser.yalniz_fola and not (yollar.emel_teslim / eser.dosya_adi).exists():
        return False  # metni Emel'li kayıtla doğrulanmamış eski eser
    teslim = gecerli_teslim(eser, yollar)
    if teslim is None:
        return True
    okuma = yollar.fola_klasoru(eser.ad) / f"{eser.ad}.mp3"
    return okuma.exists() and okuma.stat().st_mtime > teslim.stat().st_mtime  # teslimden sonra yeniden okundu


def kuyruk(katalog: Katalog, yollar: Yollar, hazirla: bool = False,
           uyar: Callable[[str], None] = lambda s: print(s, file=sys.stderr)) -> list[KuyrukIsi]:
    """Okunacak eserler, kısadan uzuna. hazirla=False: dosyaya yazmaz, uzunluk hazır okuma metninden (yoksa
    kaynaktan) ölçülür; hazirla=True: önce her eserin okuma metni kaynağına göre güncellenir (zamanlayıcı).
    Metni hazırlanamayan eser kuyruğa girmez, sebebi `uyar` ile bildirilir: tek eser bütün okumayı durdurmasın."""
    isler = []
    for e in katalog:
        if not okunacak_mi(e, yollar):
            continue
        try:
            dosya = metni_hazirla(e, yollar) if hazirla else yollar.fola_klasoru(e.ad) / "seslendirme-metni.txt"
            uzunluk = len(dosya.read_text(encoding="utf-8")) if dosya.exists() else len(okuma_metni(e, yollar))
        except MetinHatasi as h:
            uyar(f"KUYRUĞA ALINMADI: {h}")
            continue
        isler.append(KuyrukIsi(e, uzunluk, dosya))
    return sorted(isler, key=lambda x: (x.uzunluk, x.ad))
