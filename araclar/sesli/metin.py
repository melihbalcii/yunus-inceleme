"""Okuma metnini isteklere bölme (saf işlevler; ses ya da ağ yok).

Blok metinleri önbellek anahtarının parçasıdır (okuma.blok_dosyasi): buradaki arıtma ve bölme kuralları bir harf
bile değişirse önceden okunmuş bloklar tanınmaz ve kota yeniden harcanır. Kurallar eski seslendir_gemini.py ile
birebir aynıdır; testler/test_uyumluluk.py bunu gerçek eserlerin metniyle denetler.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

YUMUSAK_TIRE = "\xad"
SABIT_BLOK = 8500   # karakter; sabit planın varsayılan üst sınırı (Forsa 8306 kr tek istekte tam okundu)
EN_COK_KR = 20000   # bir isteğe sığan metin (giriş sınırı 8192 token); 20132 kr tek istekte tam okundu (28 Ekim)
UZUN_PARAGRAF = 6000


@dataclass(frozen=True)
class Paragraf:
    metin: str
    devam: bool  # önceki paragrafın sürmesi (uzun paragraf bölündü): araya paragraf boşluğu konmaz


def _arit(p: str, siir: bool) -> str:
    p = p.replace(YUMUSAK_TIRE, "")
    if siir:
        return "\n".join(re.sub(r"[ \t]+", " ", s).strip() for s in p.splitlines() if s.strip())
    return re.sub(r"\s+", " ", p)


def _sessiz_mi(p: str) -> bool:
    """"— ....." gibi, okunacak sözcüğü olmayan satır (metinde susma anı): paragraf arası duraklaması yeter."""
    return not re.search(r"\w", p)


def cumleler(metin: str) -> list[str]:
    """Metni cümlelere böler."""
    return [c for c in re.split(r"(?<=[.!?…])\s+|(?<=[.!?…][\"”»’])\s+|\n\n", metin) if c and c.strip()]


def sabit_bloklar(yazi: str, siir: bool = False, en_cok: int | None = None) -> list[str]:
    """Sabit plan: ardışık paragraflar eşit boylu bloklarda birleşir (9059 kr → 2 × ~4530, 8500 + 559 değil)."""
    sinir = en_cok or SABIT_BLOK
    toplam = len(yazi)
    sinir = -(-toplam // -(-toplam // sinir)) + 200
    sonuc: list[str] = []
    birikim: list[str] = []
    for ham in yazi.split("\n\n"):
        ham = ham.strip()
        if not ham:
            continue
        p = _arit(ham, siir)
        if _sessiz_mi(p):
            continue
        if birikim and sum(len(x) for x in birikim) + len(p) > sinir:
            sonuc.append("\n\n".join(birikim))
            birikim = []
        birikim.append(p)
    if birikim:
        sonuc.append("\n\n".join(birikim))
    return sonuc


def paragraflar(yazi: str, siir: bool = False, en_cok: int = UZUN_PARAGRAF) -> list[Paragraf]:
    """Uyarlamalı plan için arıtılmış paragraflar; en_cok'tan uzun paragraf cümle sınırından parçalanır."""
    sonuc: list[Paragraf] = []
    for ham in yazi.split("\n\n"):
        ham = ham.strip().replace(YUMUSAK_TIRE, "")
        if not ham:
            continue
        p = _arit(ham, siir)
        if _sessiz_mi(p):
            continue
        if len(p) <= en_cok:
            sonuc.append(Paragraf(p, False))
            continue
        parca, ilk = "", True
        for c in cumleler(p):
            if parca and len(parca) + len(c) + 1 > en_cok * 2 // 3:
                sonuc.append(Paragraf(parca, not ilk))
                parca, ilk = "", False
            parca = f"{parca} {c}" if parca else c
        sonuc.append(Paragraf(parca, not ilk))
    return sonuc


def birlestir(par: list[Paragraf]) -> str:
    return "".join((" " if p.devam else "\n\n") + p.metin if i else p.metin for i, p in enumerate(par))


def sonraki_sinir(par: list[Paragraf], i: int, hiz: float, hedef_sn: float) -> int:
    """par[i:]'den bir sonraki bloğun bitiş indisi: hedef ≈ hedef_sn × hiz karakter. Kalan eşit parçalara bölünür ki
    son blok cılız kalmasın (istek sayısı aynı kalır, her blok sınırdan uzak durur)."""
    hedef = min(hedef_sn * hiz, EN_COK_KR)
    kalan = sum(len(p.metin) for p in par[i:])
    if kalan <= hedef * 1.08:
        return len(par)
    pay = kalan / -(-kalan // hedef)
    j, top = i, 0
    while j < len(par) and (j == i or top + len(par[j].metin) <= min(pay * 1.04, EN_COK_KR)):
        top += len(par[j].metin)
        j += 1
    return j


def dosyadan(yol: Path) -> str:
    return yol.read_text(encoding="utf-8")
