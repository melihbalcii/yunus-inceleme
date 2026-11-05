"""Bir eseri tek araçla okutup podcast/<eser>/fola/<eser>.mp3'ü üretir.

Her blok okunur okunmaz Whisper ve ses kalitesiyle ölçülür; eşik tutmazsa önce yama, sonra yeniden okuma denenir,
en iyisi tutulur. Bloklar .tmp/gemini-parcalar/<özet>.wav önbelleğindedir: yarıda kalan eser ertesi gün kaldığı
yerden sürer. Özet = md5(metin|model|ses|üslup); aynı eseri ortak okuyan araçların blokları da geçerlidir.

Kota güvenliği: bir bloğun her denemesi okunur okunmaz diske yazılır (<özet>.deneme-N.wav, ölçümü
<özet>.denemeler.json'da). Kota ya da hata yarıda keserse ertesi gün kayıtlı denemeler kullanılır, aynı ses ikinci
kez istenmez. Bir blok için kotayı harcayabilecek istek, kota günü başına en çok BLOK_TAVANI'dır (bağlantı
tekrarları ve yama dahil). İkiye bölünen bloğun yarıları da kendi önbellek dosyalarına yazılır.

Planlar:
  uyarlamalı  her istek ≈ hedef_sn saniyelik ses; blok sınırları okunan hızdan hesaplanır, blok-plan.json'da kalır
  sabit       ardışık paragraflar eşit boylu bloklarda (3.1 için 2000 kr: güvenlik filtresi uzunluğa takılıyor)

Çıktılar (fola/ içinde): <eser>.mp3, plan.json (blok no, dosya, metin), kalite.json (blok başı/sonu kalite puanı).
"""
from __future__ import annotations

import hashlib
import itertools
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from collections.abc import Callable

import numpy as np

from . import metin as M
from . import olcum
from . import ses as S
from .gemini import USLUP, BosYanit, GeciciHata, GuvenlikReddi, TTSHatasi
from .kota import kota_gunu
from .karsilastir import olcum as blok_olcumu
from .yollar import Yollar
from .yama import yamala as varsayilan_yama
from .gemini import KotaDoldu

ESIK = 0.95         # Whisper eşleşmesi (harf düzeyinde); altındaki blok yeniden okutulur
DENEME = 3
BLOK_TAVANI = 4     # kota günü başına bir blok için kotayı harcayabilecek en çok istek
TEK_ISTEK_BUTCESI = 2  # bir uret çağrısı: ilk istek + yanıtı kaybolursa bir tekrar
YAMA_ESIGI = 0.85   # bundan iyi okunmuş ama eşiği tutmayan blok önce yamayla onarılır
BLOK_ARASI = 0.8    # sn
ILK_BLOK_PAYI = 0.88  # eserin hızı bilinmezken modelin hızının bu kadarı (diyalog ağırlıklı eser yavaş okunur)


class Seslendirici(Protocol):
    atilan: int  # şimdiye dek atılan, kotayı harcamış olabilecek istek sayısı

    def uret(self, metin: str, en_cok: int = ...) -> S.Dalga: ...


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
    return hashlib.md5(f"{metin}|{model}|{ses}|{USLUP}".encode(), usedforsecurity=False).hexdigest()[:12]


def blok_dosyasi(klasor: Path, metin: str, ayar: OkumaAyari) -> Path:
    """Bloğun önbellek dosyası: ortak araçlardan biri okuduysa onunki, yoksa bu aracınki (henüz olmayabilir)."""
    for m in (ayar.model, *ayar.ortak):
        d = klasor / f"{blok_ozeti(metin, m, ayar.ses)}.wav"
        if d.exists():
            return d
    return klasor / f"{blok_ozeti(metin, ayar.model, ayar.ses)}.wav"


@dataclass
class Deneme:
    """Bir bloğun bir okuması ve ölçümü."""
    dosya: str
    oran: float
    eksik: list[str]
    bas: float
    son: float

    @property
    def bozuk(self) -> bool:
        return S.kalite_bozuk(self.bas, self.son)

    @property
    def iyi(self) -> bool:
        return self.oran >= ESIK and not self.eksik and not self.bozuk

    @property
    def puan(self) -> float:
        return self.oran - 0.1 * len(self.eksik) - (1 if self.bozuk else 0)


class DenemeDeposu:
    """Bir bloğun bitmemiş denemeleri: <özet>.deneme-N.wav ve <özet>.denemeler.json (ölçümler, bugünkü istek
    sayısı). Blok tamamlanınca silinir. İstek sayısı kota günü değişince sıfırlanır (bağlantı kesintisi bloğu kalıcı
    kilitlemesin). Gelen ses ölçülmeden önce "bekleyen" olarak yazılır: ölçüm sürerken süreç ölürse ses kaybolmaz,
    yeniden açılışta ölçülür (H-018)."""

    def __init__(self, klasor: Path, ozet: str, gun: Callable[[], str] = kota_gunu):
        self.klasor, self.ozet, self._gun = klasor, ozet, gun
        self._kayit = klasor / f"{ozet}.denemeler.json"
        veri: dict[str, Any] = {}
        if self._kayit.exists():
            try:
                veri = json.loads(self._kayit.read_text(encoding="utf-8"))
            except ValueError:
                veri = {}
        self.denemeler = [x for d in veri.get("denemeler", []) if (x := self._deneme(d)) is not None]
        self.bekleyen = [d for d in veri.get("bekleyen", []) if self._gecerli(d) and (klasor / d).exists()]
        self.istek = int(veri.get("istek", 0)) if veri.get("gun") == gun() else 0
        self.bolunecek = bool(veri.get("bolunecek"))  # model bu bloğa bütün olarak ses vermiyor: yarılarıyla okunur

    def _gecerli(self, dosya: object) -> bool:
        """Dosya adı kayıttan okunup açılıyor ve siliniyor: yalnız bu bloğun "<özet>.deneme-N.wav" biçimindeki adı
        kabul edilir (CWE-22: "../" ile başka dosyaya ulaşılmasın)."""
        bicim = rf"{re.escape(self.ozet)}\.deneme-\d{{1,2}}\.wav"
        return isinstance(dosya, str) and re.fullmatch(bicim, dosya) is not None

    def _deneme(self, d: object) -> Deneme | None:
        if not isinstance(d, dict) or not self._gecerli(d.get("dosya")):
            return None
        try:
            deneme = Deneme(d["dosya"], float(d["oran"]), [str(x) for x in d["eksik"]],
                            float(d["bas"]), float(d["son"]))
        except (KeyError, TypeError, ValueError):
            return None
        return deneme if (self.klasor / deneme.dosya).exists() else None

    def oku(self, dosya: str) -> S.Dalga:
        return S.wav_oku(self.klasor / dosya)

    def ses(self, d: Deneme) -> S.Dalga:
        return self.oku(d.dosya)

    def sakla(self, ses: S.Dalga) -> str:
        """Gelen sesi ölçmeden önce diske yazar; adı döner."""
        dosya = f"{self.ozet}.deneme-{len(self.denemeler) + len(self.bekleyen) + 1}.wav"
        S.wav_yaz(self.klasor / dosya, ses)
        self.bekleyen.append(dosya)
        self.kaydet()
        return dosya

    def ekle(self, dosya: str, oran: float, eksik: list[str], bas: float, son: float) -> Deneme:
        d = Deneme(dosya, oran, eksik, bas, son)
        if dosya in self.bekleyen:
            self.bekleyen.remove(dosya)
        self.denemeler.append(d)
        self.kaydet()
        return d

    def kaydet(self) -> None:
        _json_yaz(self._kayit, {"gun": self._gun(), "istek": self.istek, "bolunecek": self.bolunecek,
                                "denemeler": [vars(d) for d in self.denemeler], "bekleyen": self.bekleyen})

    def temizle(self) -> None:
        for dosya in [d.dosya for d in self.denemeler] + self.bekleyen:
            (self.klasor / dosya).unlink(missing_ok=True)
        self._kayit.unlink(missing_ok=True)


class _ButceBitti(Exception):
    """Bloğun bugünkü istek bütçesi bitti; eldeki en iyi deneme kullanılır (seslendir içinde kalır)."""


class Okuyucu:
    def __init__(self, tts: Seslendirici, ayar: OkumaAyari, yollar: Yollar, *, bildir: Callable[[str], None] = print,
                 olc: Callable[[str, S.Dalga], tuple[float, list[str]]] | None = None,
                 kalite: Callable[[S.Dalga], tuple[float, float]] = S.kalite,
                 yamala: Callable[..., S.Dalga | None] | None = None,
                 gun: Callable[[], str] = kota_gunu):
        self.tts, self.ayar, self.yollar, self.bildir = tts, ayar, yollar, bildir
        self._olc = olc or (lambda metin, ses: blok_olcumu(metin, S.dok(ses)))
        self._kalite = kalite
        if yamala is None:
            yamala = varsayilan_yama
        self._yamala = yamala
        self._gun = gun

    # --- tek blok ---

    def _depo(self, metin: str) -> DenemeDeposu:
        return DenemeDeposu(self.yollar.parcalar, blok_ozeti(metin, self.ayar.model, self.ayar.ses), self._gun)

    def _iste(self, depo: DenemeDeposu, metin: str, en_cok: int) -> S.Dalga:
        """Bütçe içinde tek seslendirme çağrısı. Bütçe istekten ÖNCE harcanmış sayılıp diske yazılır, harcanmayan
        kısmı sonra iade edilir: istek sürerken süreç ölürse sayaç fazla sayar, eksik saymaz (H-017)."""
        kalan = BLOK_TAVANI - depo.istek
        if kalan < 1:
            raise GeciciHata(f"blok için bugün {BLOK_TAVANI} istek harcandı; yeni istek atılmıyor")
        ayrilan = min(en_cok, kalan)
        depo.istek += ayrilan
        depo.kaydet()
        once = self.tts.atilan
        try:
            return self.tts.uret(metin, en_cok=ayrilan)
        finally:
            depo.istek -= ayrilan - min(ayrilan, self.tts.atilan - once)
            depo.kaydet()

    def seslendir(self, metin: str, etiket: str) -> S.Dalga:
        """Bloğu okutur, ölçer, eşik tutmazsa yama ya da yeniden okuma dener; boş yanıtta ikiye böler. Her deneme
        hemen diske yazılır; daha önce kayıtlı denemeler yeniden istenmez."""
        depo = self._depo(metin)
        if depo.bolunecek:
            return self._bolerek(metin, etiket)
        kayitli = self._kayitli_iyi(depo, metin, etiket)
        if kayitli is not None:
            return kayitli
        while len(depo.denemeler) < self.ayar.deneme and depo.istek < BLOK_TAVANI:
            try:
                ses = self._bir_deneme(depo, metin, etiket)
            except _ButceBitti:
                break  # bugünkü bütçe bitti: eldeki en iyi deneme tutulur
            if ses is not None:
                return ses
        if not depo.denemeler:
            raise GeciciHata(f"blok için bugün {BLOK_TAVANI} istek harcandı, ses alınamadı")
        en_iyi = max(depo.denemeler, key=lambda d: d.puan)  # eşik tutmasa da en iyisi; kontrol raporu gösterir
        return depo.ses(en_iyi)

    def _kayitli_iyi(self, depo: DenemeDeposu, metin: str, etiket: str) -> S.Dalga | None:
        """Ölçülmeden kalmış okumaları ölçer (istek atmaz); eşiği tutan kayıtlı deneme varsa onun sesi."""
        for dosya in list(depo.bekleyen):
            self.bildir(f"{etiket} ölçülmeden kalmış okuma ölçülüyor (yeni istek yok): {dosya}")
            self._degerlendir(depo, metin, dosya, depo.oku(dosya), etiket)
        for d in depo.denemeler:
            self.bildir(f"{etiket} kayıtlı deneme kullanılıyor: {d.dosya} (eşleşme {d.oran:.3f})")
            if d.iyi:
                return depo.ses(d)
        return None

    def _bir_deneme(self, depo: DenemeDeposu, metin: str, etiket: str) -> S.Dalga | None:
        """Bir okuma isteği (gerekirse yama). Tutan ses ya da None (yeniden denenebilir). Boş yanıt ve bölünebilir
        güvenlik reddinde blok ikiye bölünür. Elde deneme varken bütçe biterse _ButceBitti."""
        try:
            ses = self._iste(depo, metin, TEK_ISTEK_BUTCESI)
        except GuvenlikReddi as h:
            if not h.bolunebilir:
                raise
            return self._bolunecek(depo, metin, etiket)
        except BosYanit:
            return self._bolunecek(depo, metin, etiket)
        except GeciciHata as h:
            if depo.denemeler:
                raise _ButceBitti from h
            raise
        d = self._degerlendir(depo, metin, depo.sakla(ses), ses, etiket)
        if d.iyi:
            return ses
        if not d.bozuk and d.oran >= YAMA_ESIGI and depo.istek < BLOK_TAVANI:
            return self._yamayi_dene(depo, metin, ses, etiket)
        return None

    def _degerlendir(self, depo: DenemeDeposu, metin: str, dosya: str, ses: S.Dalga, etiket: str) -> Deneme:
        """Diske yazılmış bir okumayı ölçer ve deneme olarak kaydeder (istek atmaz)."""
        oran, eksik = self._olc(metin, ses)
        k_bas, k_son = self._kalite(ses)
        d = depo.ekle(dosya, oran, eksik, k_bas, k_son)
        no = len(depo.denemeler)
        olcum.yaz(self.yollar.olcum, self.ayar.model, kr=len(metin), sn=round(len(ses) / S.SR, 1),
                  oran=round(oran, 4), iyi=d.iyi, atlama=len(eksik), kalite=[round(k_bas, 2), round(k_son, 2)])
        self.bildir(f"{etiket} {len(metin)} kr, {len(ses) / S.SR:.0f} sn, eşleşme {oran:.3f}, "
                    f"ses kalitesi {k_bas:.1f}→{k_son:.1f}" + (f", ATLAMA: {eksik}" if eksik else "")
                    + (", SES BOZULUYOR" if d.bozuk else "") + ("" if d.iyi else f" (deneme {no}/{self.ayar.deneme})"))
        return d

    def _yamayi_dene(self, depo: DenemeDeposu, metin: str, ses: S.Dalga, etiket: str) -> S.Dalga | None:
        try:  # yama tek istektir: yanıtı kaybolursa tekrar edilmez
            onarilmis = self._yamala(metin, ses, lambda m: self._iste(depo, m, 1), ESIK, bildir=self.bildir)
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

    def _bolunecek(self, depo: DenemeDeposu, metin: str, etiket: str) -> S.Dalga:
        # Yarıda kalırsa ertesi gün bütün blok yeniden istenmesin diye işaretlenir. Tek paragraflık blok bölünemez:
        # işaretlenmez (boş yanıt geçici olabilir; işaret kalırsa blok bir daha hiç denenmezdi).
        if len(metin.split("\n\n")) > 1:
            depo.bolunecek = True
            depo.kaydet()
        return self._bolerek(metin, etiket)

    def _bolerek(self, metin: str, etiket: str) -> S.Dalga:
        paragraf = metin.split("\n\n")
        if len(paragraf) <= 1:
            raise BolunemezHata(f"ses üretilemedi, bölünemiyor: {metin[:80]}")
        yari = sum(len(x) for x in paragraf) / 2
        birikim = list(itertools.accumulate(len(x) for x in paragraf))
        i = next((k for k, b in enumerate(birikim) if b >= yari), len(paragraf) - 1)
        i = max(1, min(i, len(paragraf) - 1))
        self.bildir(f"{etiket} ikiye bölünüyor ({len(metin)} kr)")
        # yarılar kendi önbellek dosyalarına yazılır: sağ yarı hata verirse okunmuş sol yarı yeniden istenmez
        _, sol = self._blok("\n\n".join(paragraf[:i]), etiket + "a")
        _, sag = self._blok("\n\n".join(paragraf[i:]), etiket + "b")
        return np.concatenate([sol, S.sessizlik(BLOK_ARASI), sag])

    def _blok(self, metin: str, etiket: str) -> tuple[Path, S.Dalga]:
        dosya = blok_dosyasi(self.yollar.parcalar, metin, self.ayar)
        if dosya.exists():
            return dosya, S.wav_oku(dosya)
        ses = self.seslendir(metin, etiket)
        S.wav_yaz(dosya, ses)
        self._depo(metin).temizle()
        return dosya, ses

    # --- planlar ---

    def _uyarlamali(self, yazi: str, plan_dosyasi: Path, hedef_sn: int) -> list[tuple[Path, str]]:
        par = M.paragraflar(yazi, self.ayar.siir)
        kimlik = dict(model=self.ayar.model, ses=self.ayar.ses, uslup=USLUP, paragraf=len(par),
                      karakter=sum(len(p.metin) for p in par))
        eski, eski_sinirlar = self._plan_oku(plan_dosyasi, len(par))
        if eski.get("model") in self.ayar.ortak and {**eski, "model": self.ayar.model} == kimlik:
            kimlik = eski  # ortak aracın planı aynen sürer (sınırlar değişirse önbellekteki bloklar tutmaz)
        sinirlar: list[int] = eski_sinirlar if eski == kimlik else []
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
            if len(ses) / S.SR > olcum.HIZ_OLCUM_EN_KISA_SN:
                hizlar.append(len(metin) / (len(ses) / S.SR))
            bloklar.append((dosya, metin))
            i = j
        return bloklar

    def _plan_oku(self, plan_dosyasi: Path, paragraf_sayisi: int) -> tuple[dict[str, Any], list[int]]:
        """blok-plan.json'u doğrulayarak okur: (kimlik, sınırlar). Bozuk dosya programı düşürmez; uyarıyla yok
        sayılır."""
        if not plan_dosyasi.exists():
            return {}, []
        try:
            kayit = json.loads(plan_dosyasi.read_text())
            kimlik, sinirlar = kayit.get("kimlik") or {}, kayit.get("sinirlar", [])
            gecerli = (isinstance(kimlik, dict) and all(isinstance(v, (str, int)) for v in kimlik.values())
                       and isinstance(sinirlar, list) and all(type(x) is int for x in sinirlar)
                       and sinirlar == sorted(set(sinirlar)) and all(0 < x <= paragraf_sayisi for x in sinirlar))
        except (OSError, ValueError, AttributeError):
            gecerli = False
        if not gecerli:
            self.bildir(f"UYARI: {plan_dosyasi} bozuk, yok sayılıyor (blok sınırları yeniden hesaplanacak)")
            return {}, []
        return kimlik, sinirlar

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
