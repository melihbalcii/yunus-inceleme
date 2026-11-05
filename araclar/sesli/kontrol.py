"""Okunmuş eserin kontrolü: her blok Whisper'la yazıya dökülüp metinle karşılaştırılır.

Sonuç fola/kontrol.json'a (teslim bunu okur) ve okunabilir özeti fola/kontrol.txt'ye yazılır. Whisper dökümleri
.tmp/gemini-parcalar/yazidokum.json'da önbellektedir (anahtar: dosya adı + boyutu; blok yeniden okununca boyutu
değişir), aynı kontrol ikinci kez saniyeler sürer.

Teslim koşulu (`KontrolSonucu.gecti`): harf düzeyinde eşleşme ≥ %97, 0,90 altı blok yok, atlama yok.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from . import ses as S
from .karsilastir import harf_eslesmesi, kelimeler, olcum

ESLESME_ESIGI = 97.0
DUSUK = 0.90
IKINCI_DINLEME = 0.9  # kapsama bunun altındaysa Whisper bir parçayı atlamış olabilir: öbür kipte bir daha dinlenir


@dataclass
class BlokRaporu:
    no: int
    oran: float
    kapsama: float
    metin: str
    duyulan: str
    atlama: list[str]


@dataclass
class KontrolSonucu:
    eslesme: float                       # yüzde
    bloklar: list[BlokRaporu] = field(default_factory=list)

    @property
    def dusuk(self) -> int:
        return sum(b.oran < DUSUK for b in self.bloklar)

    @property
    def atlamalar(self) -> list[tuple[int, str]]:
        return [(b.no, a) for b in self.bloklar for a in b.atlama]

    @property
    def gecti(self) -> bool:
        return self.eslesme >= ESLESME_ESIGI and self.dusuk == 0 and not self.atlamalar

    def sorunlu_bloklar(self) -> list[int]:
        return [b.no for b in self.bloklar if b.atlama or b.oran < DUSUK]

    def yaz(self, klasor: Path) -> None:
        veri = dict(eslesme=round(self.eslesme, 2), gecti=self.gecti, bloklar=[asdict(b) for b in self.bloklar])
        _yaz(klasor / "kontrol.json", json.dumps(veri, ensure_ascii=False, indent=1))
        _yaz(klasor / "kontrol.txt", self.ozet())

    @classmethod
    def oku(cls, klasor: Path) -> "KontrolSonucu | None":
        try:
            veri = json.loads((klasor / "kontrol.json").read_text(encoding="utf-8"))
            return cls(eslesme=float(veri["eslesme"]), bloklar=[BlokRaporu(**b) for b in veri["bloklar"]])
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def ozet(self) -> str:
        s = [f"[{b.no}/{len(self.bloklar)}] {b.oran:.3f}" for b in self.bloklar]
        s += ["", f"PARAGRAF {len(self.bloklar)} | harf düzeyinde eşleşme %{self.eslesme:.2f}",
              f"0,95 altı: {sum(b.oran < 0.95 for b in self.bloklar)} | 0,90 altı: {self.dusuk}"]
        s += [f"ATLAMA #{no}: «{a}»" for no, a in self.atlamalar]
        s += [f"KAPSAMA DÜŞÜK #{b.no} %{100 * b.kapsama:.0f} (metnin bu kadarı seste duyuldu)"
              for b in sorted(self.bloklar, key=lambda b: b.kapsama)[:5] if b.kapsama < IKINCI_DINLEME]
        s += [f"- #{b.no} {b.oran:.3f}\n  metin  : {b.metin[:200]}\n  duyulan: {b.duyulan[:200]}"
              for b in sorted(self.bloklar, key=lambda b: b.oran)[:12]]
        return "\n".join(s) + "\n"


def kontrol_et(fola: Path, parcalar: Path, bildir: Callable[[str], None] = print,
               dok: Callable[[Path, bool], str] | None = None) -> KontrolSonucu:
    """fola/plan.json'daki blokları denetler, sonucu fola/ altına yazar."""
    plan = json.loads((fola / "plan.json").read_text(encoding="utf-8"))
    dok = dok or (lambda dosya, kosullu: S.dok(S.wav_oku(dosya), onceki_metne_bagli=kosullu))
    onbellek_yolu = parcalar / "yazidokum.json"
    onbellek: dict[str, str] = json.loads(onbellek_yolu.read_text(encoding="utf-8")) if onbellek_yolu.exists() else {}

    def dokum(anahtar: str, dosya: Path, kosullu: bool) -> str:
        if anahtar not in onbellek:
            onbellek[anahtar] = dok(dosya, kosullu)
            _yaz(onbellek_yolu, json.dumps(onbellek, ensure_ascii=False, indent=1))
        return onbellek[anahtar]

    bloklar, top_hedef, top_eslesen = [], 0, 0
    for p in plan:
        if not p.get("dosya"):
            continue
        dosya = parcalar / p["dosya"]
        anahtar = f'{p["dosya"]}|{dosya.stat().st_size}'
        duyulan = dokum(anahtar, dosya, False)
        oran, eslesen, harf = harf_eslesmesi(p["metin"], duyulan)
        # Whisper uzun blokta bazen bir parçayı atlıyor (ses tam olduğu hâlde): öbür kipte bir daha dinlet
        if eslesen / max(1, harf) < IKINCI_DINLEME and len(kelimeler(p["metin"])) > 8:
            ikinci = dokum(anahtar + "|2", dosya, True)
            o2, e2, _ = harf_eslesmesi(p["metin"], ikinci)
            if e2 > eslesen:
                onbellek[anahtar] = ikinci
                _yaz(onbellek_yolu, json.dumps(onbellek, ensure_ascii=False, indent=1))
                duyulan, oran, eslesen = ikinci, o2, e2
        top_hedef += harf
        top_eslesen += eslesen
        _, atla = olcum(p["metin"], duyulan)
        bloklar.append(BlokRaporu(no=p["no"], oran=round(oran, 3), kapsama=round(eslesen / max(1, harf), 3),
                                  metin=p["metin"], duyulan=duyulan, atlama=atla))
        bildir(f"[{p['no']}/{len(plan)}] {oran:.3f}")
    sonuc = KontrolSonucu(eslesme=100 * top_eslesen / max(1, top_hedef), bloklar=bloklar)
    sonuc.yaz(fola)
    return sonuc


def _yaz(yol: Path, yazi: str) -> None:
    gecici = yol.with_name(yol.name + ".yaziliyor")
    gecici.write_text(yazi, encoding="utf-8")
    gecici.replace(yol)
