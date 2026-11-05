"""Okuma durumu (.tmp/fola-atama.json): hangi eser hangi araçta, hangi araç hangi eseri okuyamıyor.

Her değişiklik dosya kilidi altında "en güncel hâli oku → değiştir → geçici dosyaya yaz → yerine taşı" diye yapılır.
Eskiden program durumu bellekte tutup dosyanın üstüne yazıyordu; program çalışırken dosyada yapılan düzenleme
(ör. 4 Kasım'daki ortak okuma ayarı) sessizce siliniyordu. Artık bellekte kopya tutulmaz.

Alanlar:
  atama    {eser: model}     eseri okuyan araç (eser baştan sona tek araçla okunur)
  ortak    {eser: [model]}   eseri atanan araçla birlikte okuyabilen öbür araçlar (blokları geçerli)
  ret      {model: [eser]}   aracın okuyamadığı ya da okumaması istenen eserler
  yontem   {eser: "uyarlamali" | "eski"}  eserin blok planı (yarıda kalan eser planını değiştirmez)
  onarim   {eser: sayı}      sorunlu blokları yeniden okuma denemesi
  oncelik  [eser]            sırası beklenmeden okunacak eserler
"""
from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

UYARLAMALI = "uyarlamali"
SABIT = "eski"


@dataclass
class Durum:
    atama: dict[str, str] = field(default_factory=dict)
    ortak: dict[str, list[str]] = field(default_factory=dict)
    ret: dict[str, list[str]] = field(default_factory=dict)
    yontem: dict[str, str] = field(default_factory=dict)
    onarim: dict[str, int] = field(default_factory=dict)
    oncelik: list[str] = field(default_factory=list)
    _bilinmeyen: dict[str, Any] = field(default_factory=dict, repr=False)  # elle eklenmiş alanlar korunur

    @classmethod
    def sozlukten(cls, veri: dict[str, Any]) -> "Durum":
        bilinen = {"atama", "ortak", "ret", "yontem", "onarim", "oncelik"}
        return cls(atama=dict(veri.get("atama", {})), ortak={k: list(v) for k, v in veri.get("ortak", {}).items()},
                   ret={k: list(v) for k, v in veri.get("ret", {}).items()}, yontem=dict(veri.get("yontem", {})),
                   onarim=dict(veri.get("onarim", {})), oncelik=list(veri.get("oncelik", [])),
                   _bilinmeyen={k: v for k, v in veri.items() if k not in bilinen})

    def sozluk(self) -> dict[str, Any]:
        return {"atama": self.atama, "ret": self.ret, "yontem": self.yontem, "onarim": self.onarim,
                "oncelik": self.oncelik, "ortak": self.ortak, **self._bilinmeyen}

    # --- sorgular ---

    def reddedildi_mi(self, model: str, eser: str) -> bool:
        return eser in self.ret.get(model, [])

    def ortaklar(self, eser: str) -> list[str]:
        return list(self.ortak.get(eser, []))

    def okuyabilir_mi(self, model: str, eser: str) -> bool:
        """Araç bu esere atanmış ya da ortak okuyucusu."""
        return self.atama.get(eser) == model or model in self.ortak.get(eser, [])

    # --- değişiklikler ---

    def reddet(self, model: str, eser: str) -> None:
        self.atama.pop(eser, None)
        liste = self.ret.setdefault(model, [])
        if eser not in liste:
            liste.append(eser)

    def bitir(self, eser: str) -> None:
        self.atama.pop(eser, None)
        self.ortak.pop(eser, None)


class DurumDeposu:
    def __init__(self, dosya: Path):
        self.dosya = dosya
        self._kilit = dosya.with_name(dosya.name + ".kilit")

    @contextmanager
    def _kilitli(self) -> Iterator[None]:
        self.dosya.parent.mkdir(parents=True, exist_ok=True)
        with open(self._kilit, "a") as k:
            fcntl.flock(k, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(k, fcntl.LOCK_UN)

    def _oku(self) -> Durum:
        if not self.dosya.exists():
            return Durum()
        return Durum.sozlukten(json.loads(self.dosya.read_text(encoding="utf-8")))

    def oku(self) -> Durum:
        with self._kilitli():
            return self._oku()

    @contextmanager
    def degistir(self) -> Iterator[Durum]:
        """with depo.degistir() as d: ...  — blok hatasız biterse değişiklik yazılır, hata olursa hiçbir şey yazılmaz."""
        with self._kilitli():
            d = self._oku()
            yield d
            gecici = self.dosya.with_name(self.dosya.name + ".yaziliyor")
            gecici.write_text(json.dumps(d.sozluk(), ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(gecici, self.dosya)
