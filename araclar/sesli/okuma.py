"""Bir eseri tek araçla okutup podcast/<eser>/fola/<eser>.mp3'ü üretir.

Her blok okunur okunmaz Whisper ve ses kalitesiyle ölçülür; eşik tutmazsa önce yama, sonra yeniden okuma denenir,
en iyisi tutulur. Bloklar .tmp/gemini-parcalar/<özet>.wav önbelleğindedir: yarıda kalan eser ertesi gün kaldığı
yerden sürer. Özet = md5(metin|model|ses|üslup); aynı eseri ortak okuyan araçların blokları da geçerlidir.

Planlar:
  uyarlamalı  her istek ≈ hedef_sn saniyelik ses; blok sınırları okunan hızdan hesaplanır, blok-plan.json'da kalır
  sabit       ardışık paragraflar eşit boylu bloklarda (3.1 için 2000 kr: güvenlik filtresi uzunluğa takılıyor)

Çıktılar (fola/ içinde): <eser>.mp3, plan.json (blok no, dosya, metin), kalite.json (blok başı/sonu kalite puanı).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

import numpy as np

from . import metin as M
from . import olcum
from . import ses as S
from .gemini import USLUP, BosYanit, GuvenlikReddi, TTSHatasi
from .karsilastir import olcum as blok_olcumu
from .yollar import Yollar

ESIK = 0.95         # Whisper eşleşmesi (harf düzeyinde); altındaki blok yeniden okutulur
DENEME = 3
YAMA_ESIGI = 0.85   # bundan iyi okunmuş ama eşiği tutmayan blok önce yamayla onarılır
BLOK_ARASI = 0.8    # sn
ILK_BLOK_PAYI = 0.88  # eserin hızı bilinmezken modelin hızının bu kadarı (diyalog ağırlıklı eser yavaş okunur)


class Seslendirici(Protocol):
    def uret(self, metin: str) -> S.Dalga: ...


class BolunemezHata(TTSHatasi):
    """Boş yanıt dönen blok tek paragraftan oluşuyor; daha küçük parçaya bölünemiyor."""


@dataclass
class OkumaAyari:
    model: str
    ses: str
    ortak: tuple[str, ...] = ()   # bu eseri ortak okuyan öbür modeller: onların blokları ve planı da geçerli
    hedef_sn: int | None = None   # uyarlamalı plan
    sabit_blok: int | None = None  # sabit plan sınırı (hedef_sn yoksa)
    siir: bool = False
    deneme: int = DENEME


def blok_ozeti(metin: str, model: str, ses: str) -> str:
    return hashlib.md5(f"{metin}|{model}|{ses}|{USLUP}".encode()).hexdigest()[:12]


def blok_dosyasi(klasor: Path, metin: str, ayar: OkumaAyari) -> Path:
    """Bloğun önbellek dosyası: ortak araçlardan biri okuduysa onunki, yoksa bu aracınki (henüz olmayabilir)."""
    for m in (ayar.model, *ayar.ortak):
        d = klasor / f"{blok_ozeti(metin, m, ayar.ses)}.wav"
        if d.exists():
            return d
    return klasor / f"{blok_ozeti(metin, ayar.model, ayar.ses)}.wav"


class Okuyucu:
    def __init__(self, tts: Seslendirici, ayar: OkumaAyari, yollar: Yollar, bildir: Callable[[str], None] = print,
                 olc: Callable[[str, S.Dalga], tuple[float, list[str]]] | None = None,
                 kalite: Callable[[S.Dalga], tuple[float, float]] = S.kalite,
                 yamala: Callable[..., S.Dalga | None] | None = None):
        self.tts, self.ayar, self.yollar, self.bildir = tts, ayar, yollar, bildir
        self._olc = olc or (lambda metin, ses: blok_olcumu(metin, S.dok(ses)))
        self._kalite = kalite
        if yamala is None:
            from .yama import yamala as _y
            yamala = _y
        self._yamala = yamala

    # --- tek blok ---

    def seslendir(self, metin: str, etiket: str) -> S.Dalga:
        """Bloğu okutur, ölçer, eşik tutmazsa yama ya da yeniden okuma dener; boş yanıtta ikiye böler."""
        en_iyi: tuple[float, S.Dalga] | None = None
        for d in range(self.ayar.deneme):
            try:
                ses = self.tts.uret(metin)
            except GuvenlikReddi as h:
                if not h.bolunebilir:
                    raise
                return self._bolerek(metin, etiket)
            except BosYanit:
                return self._bolerek(metin, etiket)
            oran, eksik = self._olc(metin, ses)
            k_bas, k_son = self._kalite(ses)
            bozuk = S.kalite_bozuk(k_bas, k_son)
            iyi = oran >= ESIK and not eksik and not bozuk
            olcum.yaz(self.yollar.olcum, self.ayar.model, kr=len(metin), sn=round(len(ses) / S.SR, 1),
                      oran=round(oran, 4), iyi=iyi, atlama=len(eksik), kalite=[round(k_bas, 2), round(k_son, 2)])
            self.bildir(f"{etiket} {len(metin)} kr, {len(ses) / S.SR:.0f} sn, eşleşme {oran:.3f}, "
                        f"ses kalitesi {k_bas:.1f}→{k_son:.1f}" + (f", ATLAMA: {eksik}" if eksik else "")
                        + (", SES BOZULUYOR" if bozuk else "") + ("" if iyi else f" (deneme {d + 1}/{self.ayar.deneme})"))
            if not iyi and not bozuk and oran >= YAMA_ESIGI:
                onarilmis = self._yamayi_dene(metin, ses, etiket)
                if onarilmis is not None:
                    return onarilmis
            puan = oran - 0.1 * len(eksik) - (1 if bozuk else 0)
            if en_iyi is None or puan > en_iyi[0]:
                en_iyi = (puan, ses)
            if iyi:
                break
        assert en_iyi is not None
        return en_iyi[1]  # eşik tutmasa da en iyisi tutulur; kontrol raporu gösterir

    def _yamayi_dene(self, metin: str, ses: S.Dalga, etiket: str) -> S.Dalga | None:
        from .gemini import KotaDoldu
        try:
            onarilmis = self._yamala(metin, ses, self.tts.uret, ESIK, self.bildir)
        except KotaDoldu:
            raise
        except Exception as h:  # yama beklenmedik bir duruma düşerse blok eski yolla yeniden okunur
            self.bildir(f"{etiket} yama yapılamadı: {h!r}")
            return None
        if onarilmis is None:
            return None
        oran, eksik = self._olc(metin, onarilmis)
        self.bildir(f"{etiket} yamalı: eşleşme {oran:.3f}" + (f", ATLAMA: {eksik}" if eksik else ""))
        tamam = oran >= ESIK and not eksik
        olcum.yaz(self.yollar.olcum, self.ayar.model, kr=len(metin), sn=round(len(onarilmis) / S.SR, 1),
                  oran=round(oran, 4), iyi=tamam, atlama=len(eksik), yama=True)
        return onarilmis if tamam else None

    def _bolerek(self, metin: str, etiket: str) -> S.Dalga:
        paragraf = metin.split("\n\n")
        if len(paragraf) < 2:
            raise BolunemezHata(f"ses üretilemedi, bölünemiyor: {metin[:80]}")
        yari, birikim, i = sum(len(x) for x in paragraf) / 2, 0, 0
        for i, x in enumerate(paragraf):
            birikim += len(x)
            if birikim >= yari:
                break
        i = max(1, min(i, len(paragraf) - 1))
        self.bildir(f"{etiket} ikiye bölünüyor ({len(metin)} kr)")
        sol = self.seslendir("\n\n".join(paragraf[:i]), etiket + "a")
        sag = self.seslendir("\n\n".join(paragraf[i:]), etiket + "b")
        return np.concatenate([sol, S.sessizlik(BLOK_ARASI), sag])

    def _blok(self, metin: str, etiket: str) -> tuple[Path, S.Dalga]:
        dosya = blok_dosyasi(self.yollar.parcalar, metin, self.ayar)
        if dosya.exists():
            return dosya, S.wav_oku(dosya)
        ses = self.seslendir(metin, etiket)
        S.wav_yaz(dosya, ses)
        return dosya, ses

    # --- planlar ---

    def _uyarlamali(self, yazi: str, plan_dosyasi: Path, hedef_sn: int) -> list[tuple[Path, str]]:
        par = M.paragraflar(yazi, self.ayar.siir)
        kimlik = dict(model=self.ayar.model, ses=self.ayar.ses, uslup=USLUP, paragraf=len(par),
                      karakter=sum(len(p.metin) for p in par))
        kayit = json.loads(plan_dosyasi.read_text()) if plan_dosyasi.exists() else {}
        eski = kayit.get("kimlik") or {}
        if eski.get("model") in self.ayar.ortak and {**eski, "model": self.ayar.model} == kimlik:
            kimlik = eski  # ortak aracın planı aynen sürer (sınırlar değişirse önbellekteki bloklar tutmaz)
        sinirlar: list[int] = list(kayit.get("sinirlar", [])) if kayit.get("kimlik") == kimlik else []
        hizlar: list[float] = []
        bloklar: list[tuple[Path, str]] = []
        i = n = 0
        while i < len(par):
            n += 1
            if n <= len(sinirlar):
                j = sinirlar[n - 1]
            else:
                hiz = (min(sorted(hizlar)[len(hizlar) // 2], hizlar[-1]) if hizlar
                       else olcum.model_hizi(self.yollar.olcum, self.ayar.model) * ILK_BLOK_PAYI)
                j = M.sonraki_sinir(par, i, hiz, hedef_sn)
                sinirlar.append(j)
                _json_yaz(plan_dosyasi, dict(kimlik=kimlik, sinirlar=sinirlar))
            metin = M.birlestir(par[i:j])
            kalan = sum(len(p.metin) for p in par[j:])
            dosya, ses = self._blok(metin, f"[{n}] blok (kalan {kalan:,} kr)")
            if len(ses) / S.SR > 60:
                hizlar.append(len(metin) / (len(ses) / S.SR))
            bloklar.append((dosya, metin))
            i = j
        return bloklar

    def _sabit(self, yazi: str) -> list[tuple[Path, str]]:
        metinler = M.sabit_bloklar(yazi, self.ayar.siir, self.ayar.sabit_blok)
        return [(self._blok(m, f"[{n}/{len(metinler)}] blok")[0], m) for n, m in enumerate(metinler, 1)]

    # --- eser ---

    def eseri_oku(self, metin_dosyasi: Path, cikti: Path) -> float:
        """Eseri okur, MP3'ü ve plan/kalite kayıtlarını yazar; süreyi (dk) döndürür."""
        self.yollar.parcalar.mkdir(parents=True, exist_ok=True)
        yazi = metin_dosyasi.read_text(encoding="utf-8")
        if self.ayar.hedef_sn:
            bloklar = self._uyarlamali(yazi, cikti.parent / "blok-plan.json", self.ayar.hedef_sn)
        else:
            bloklar = self._sabit(yazi)
        parcalar: list[S.Dalga] = []
        plan, kalite = [], []
        for no, (dosya, metin) in enumerate(bloklar, 1):
            ses = S.wav_oku(dosya)
            parcalar += [ses, S.sessizlik(BLOK_ARASI)]
            plan.append(dict(no=no, tarz="blok", dosya=dosya.name, metin=metin))
            b, s = self._kalite(ses)
            kalite.append(dict(no=no, bas=round(b, 2), son=round(s, 2), bozuk=S.kalite_bozuk(b, s)))
        tum = np.concatenate(parcalar)
        S.mp3_yaz(cikti, tum)
        _json_yaz(cikti.parent / "plan.json", plan, girinti=1)
        _json_yaz(cikti.parent / "kalite.json", kalite, girinti=1)
        bozuk = [k["no"] for k in kalite if k["bozuk"]]
        if bozuk:
            self.bildir(f"SES KALİTESİ DÜŞÜK bloklar: {bozuk}")
        sure = len(tum) / S.SR / 60
        self.bildir(f"BITTI {cikti} süre {sure:.1f} dk")
        return sure


def _json_yaz(yol: Path, veri: object, girinti: int | None = None) -> None:
    gecici = yol.with_name(yol.name + ".yaziliyor")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=girinti), encoding="utf-8")
    gecici.replace(yol)
