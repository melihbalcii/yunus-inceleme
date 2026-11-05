"""Eser listesi: podcast/eserler.json tek kaynaktır (eskiden sesli_kitaba_kopyala.py'deki sözlükler başka betiklerce
ast ile ayrıştırılıyordu). Dosya yüklenirken doğrulanır: aynı ad ya da numara iki kez geçemez."""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Iterator

from .yollar import Yollar


class EserDurumu(StrEnum):
    ETKIN = "etkin"                # okunur, teslim edilir, sitede yer alır
    VAZGECILDI = "vazgecildi"      # kullanıcı vazgeçti: dosyalara dokunulmaz, hiçbir yerde kullanılmaz
    TAMAMLANMADI = "tamamlanmadi"  # metni tam değil: tamamlanana kadar okunmaz, teslim edilmez


class KatalogHatasi(ValueError):
    pass


@dataclass(frozen=True)
class Eser:
    ad: str            # klasör adı (podcast/<ad>)
    no: int            # klasikler-100 plan numarası; dosya adının başı
    eser: str
    yazar: str
    durum: EserDurumu
    yalniz_fola: bool  # Emel'li kopyası yok, doğrudan Fola'ya okutulur
    siir: bool         # paragraf içindeki satır sonları korunur
    not_: str = ""

    @property
    def dosya_adi(self) -> str:
        return f"{self.no:02d} - {self.eser} - {self.yazar}.mp3"

    @property
    def etkin(self) -> bool:
        return self.durum is EserDurumu.ETKIN


class Katalog:
    def __init__(self, eserler: list[Eser]):
        self._ad: dict[str, Eser] = {}
        self._no: dict[int, Eser] = {}
        for e in eserler:
            if e.ad in self._ad:
                raise KatalogHatasi(f"aynı ad iki kez: {e.ad}")
            if e.no in self._no:
                raise KatalogHatasi(f"aynı numara iki kez: {e.no} ({self._no[e.no].ad}, {e.ad})")
            self._ad[e.ad] = e
            self._no[e.no] = e

    @classmethod
    def yukle(cls, yollar: Yollar | None = None, dosya: Path | None = None) -> "Katalog":
        dosya = dosya or (yollar or Yollar.varsayilan()).eserler
        try:
            ham = json.loads(dosya.read_text(encoding="utf-8"))["eserler"]
        except (OSError, ValueError, KeyError) as h:
            raise KatalogHatasi(f"{dosya} okunamadı: {h}") from h
        eserler = []
        for k in ham:
            try:
                eserler.append(Eser(ad=str(k["ad"]), no=int(k["no"]), eser=str(k["eser"]), yazar=str(k["yazar"]),
                                    durum=EserDurumu(k["durum"]), yalniz_fola=bool(k.get("yalniz_fola", False)),
                                    siir=bool(k.get("siir", False)), not_=str(k.get("not", ""))))
            except (KeyError, ValueError, TypeError) as h:
                raise KatalogHatasi(f"geçersiz eser kaydı {k!r}: {h}") from h
        return cls(eserler)

    def __iter__(self) -> Iterator[Eser]:
        return iter(self._ad.values())

    def __len__(self) -> int:
        return len(self._ad)

    def __contains__(self, ad: str) -> bool:
        return ad in self._ad

    def al(self, ad: str) -> Eser:
        try:
            return self._ad[ad]
        except KeyError:
            raise KatalogHatasi(f"eser listesinde yok: {ad}") from None

    def numarayla(self, no: int) -> Eser | None:
        return self._no.get(no)

    def etkinler(self) -> list[Eser]:
        return [e for e in self if e.etkin]
