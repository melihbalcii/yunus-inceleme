"""Bir bloğu bütünüyle yeniden okutmadan onarma.

- Atlanan cümleler (bir ya da birkaç yerde) TEK kısa istekte birlikte okutulur, Whisper'ın kelime zamanlarıyla
  parçalanıp her biri kendi yerine konur. Kısa istek neredeyse hiç atlamaz (Usher: 71 kr yama %100).
- Modelin metinde olmayan, en az 4 kelimelik eklemesi istek harcamadan kesilip atılır.
Kesimler komşu kelimeler arasındaki duraklamanın ortasından yapılır. Onarım güvenle yapılamıyorsa None döner;
çağıran bütün bloğu yeniden dener.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np

from . import ses as S
from .karsilastir import atlamalar, kayip_mi, sade_kelimeler
from .metin import cumleler

EN_COK_YER = 4
EN_COK_YAMA_KR = 4000

KelimeZamani = tuple[str, float, float]
Eslesme = tuple[Sequence[tuple[str, int, int, int, int]], dict[int, int], list[str]]


@dataclass
class _Kesim:
    """Blok sesinden [t0, t1) aralığı atılır; yerine (varsa) `yazi`nın yama isteğinde okunmuş sesi konur."""
    t0: float
    t1: float
    yazi: str | None = None
    ses: S.Dalga | None = None


def _eslestir(hedef: list[str], duy: list[KelimeZamani]) -> Eslesme:
    h = [x[0] for x in duy]
    ops = difflib.SequenceMatcher(None, hedef, h, autojunk=False).get_opcodes()
    es = {i1 + d: j1 + d for op, i1, i2, j1, j2 in ops if op == "equal" for d in range(i2 - i1)}
    return ops, es, h


def _ara_nokta(duy: list[KelimeZamani], j: int, sure: float) -> float:
    """duy[j-1] ile duy[j] arasındaki duraklamanın ortası (sn)."""
    if j <= 0:
        return 0.0
    if j >= len(duy):
        return sure
    return (duy[j - 1][2] + duy[j][1]) / 2


def yamala(metin: str, ses: S.Dalga, uret: Callable[[str], S.Dalga], esik: float,
           bildir: Callable[[str], None] = print,
           kelime_zamanlari: Callable[[S.Dalga], list[KelimeZamani]] = S.kelime_zamanlari) -> S.Dalga | None:
    """`uret` bir metni seslendiren istektir (gemini.GeminiTTS.uret); TTSHatasi fırlatırsa onarım yapılamamış sayılır,
    KotaDoldu ise yukarı iletilir."""
    from .gemini import BosYanit, GuvenlikReddi

    duy = kelime_zamanlari(ses)
    cumle = cumleler(metin)
    hedef: list[str] = []
    hangi: list[int] = []
    for i, c in enumerate(cumle):
        k = sade_kelimeler(c)
        hedef += k
        hangi += [i] * len(k)
    if hedef != sade_kelimeler(metin) or not duy:
        return None
    ops, es, h = _eslestir(hedef, duy)
    sure = len(ses) / S.SR
    bolgeler: list[list[int]] = []
    atilacak: list[tuple[float, float]] = []
    for op, i1, i2, j1, j2 in ops:
        if op in ("delete", "replace") and kayip_mi(hedef[i1:i2], h[j1:j2]):
            a, b = hangi[i1], hangi[i2 - 1]
            if bolgeler and a <= bolgeler[-1][1] + 1:
                bolgeler[-1][1] = max(bolgeler[-1][1], b)
            else:
                bolgeler.append([a, b])
        elif op == "insert" and j2 - j1 >= 4 and len("".join(h[j1:j2])) >= 15:
            atilacak.append((_ara_nokta(duy, j1, sure), _ara_nokta(duy, j2, sure)))
    if len(bolgeler) > EN_COK_YER:
        return None

    kesim: list[_Kesim] = []
    for a, b in bolgeler:
        ilk = hangi.index(a)
        son = len(hangi) - 1 - hangi[::-1].index(b)
        once = [es[i] for i in range(ilk) if i in es]
        sonra = [es[i] for i in range(son + 1, len(hedef)) if i in es]
        if once and sonra and sonra[0] <= once[-1]:
            return None
        kesim.append(_Kesim(_ara_nokta(duy, once[-1] + 1, sure) if once else 0.0,
                            _ara_nokta(duy, sonra[0], sure) if sonra else sure, " ".join(cumle[a:b + 1])))
    kesim += [_Kesim(t0, t1) for t0, t1 in atilacak if not any(k.t0 <= t0 < k.t1 for k in kesim)]
    if not kesim:
        return None

    yazilar = [k.yazi for k in kesim if k.yazi]
    if sum(len(x) for x in yazilar) > EN_COK_YAMA_KR:
        return None
    if yazilar:
        yama_metni = "\n\n".join(yazilar)
        try:
            y = uret(yama_metni)
        except (BosYanit, GuvenlikReddi):
            return None
        yduy = kelime_zamanlari(y)
        yhedef: list[str] = []
        ybolge: list[int] = []
        for n, x in enumerate(yazilar):
            k = sade_kelimeler(x)
            yhedef += k
            ybolge += [n] * len(k)
        oran = difflib.SequenceMatcher(None, "".join(yhedef), "".join(x[0] for x in yduy), autojunk=False).ratio()
        eksik = atlamalar(yhedef, [x[0] for x in yduy])
        bildir(f"   yama: {len(yazilar)} yer, {len(yama_metni)} kr tek istekte, {len(y) / S.SR:.1f} sn, "
               f"eşleşme {oran:.3f}" + (f", ATLAMA: {eksik}" if eksik else ""))
        if oran < esik or eksik:
            return None
        _, yes, _ = _eslestir(yhedef, yduy)
        ysure, sinir = len(y) / S.SR, [0.0]
        for n in range(1, len(yazilar)):  # n-1. ve n. yama parçası arasındaki duraklama
            son_ = [yes[i] for i in range(len(yhedef)) if ybolge[i] == n - 1 and i in yes]
            ilk_ = [yes[i] for i in range(len(yhedef)) if ybolge[i] == n and i in yes]
            if not son_ or not ilk_ or ilk_[0] <= son_[-1]:
                return None
            sinir.append(_ara_nokta(yduy, ilk_[0], ysure))
        sinir.append(ysure)
        parca = iter(S.kirp(y[int(sinir[n] * S.SR):int(sinir[n + 1] * S.SR)]) for n in range(len(yazilar)))
        for kes in kesim:
            if kes.yazi:
                kes.ses = next(parca)
    else:
        bildir(f"   yama: yalnız {len(kesim)} fazla okuma kesildi (istek harcanmadı)")

    bosluk = S.sessizlik(0.25)
    parcalar: list[S.Dalga] = []
    simdi = 0.0
    for kes in sorted(kesim, key=lambda k: k.t0):
        if kes.t0 < simdi:
            return None
        parcalar.append(ses[int(simdi * S.SR):int(kes.t0 * S.SR)])
        if kes.ses is not None:
            parcalar += [bosluk if kes.t0 > 0 else bosluk[:0], kes.ses, bosluk]
        simdi = kes.t1
    parcalar.append(ses[int(simdi * S.SR):])
    return np.concatenate(parcalar)
