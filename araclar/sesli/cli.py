"""Komut satırı. Kullanım: .venv-ses/bin/python araclar/sesli_kitap.py <komut> [seçenekler]

  durum               eserlerin ve okuma araçlarının durumu (hiçbir şeyi değiştirmez)
  oku                 zamanlayıcıyı başlatır: kuyruk bitene dek okur, kontrol eder, teslim eder
  kontrol AD          okunmuş eseri yeniden kontrol eder (Whisper önbellekten; istek atmaz)
  teslim [AD]         kontrolden geçmiş okumaları teslim klasörüne koyar
  ceviri AD           tr/NN.md bölümlerinden ceviri.txt ve seslendirme-metni.txt üretir
  hazirla AD          okuma metnini (fola/seslendirme-metni.txt) kaynağından günceller
  site [--kuru]       site yayın klasörünü hazırlar (yayına almaz)
  oku-eser AD …       (iç kullanım) zamanlayıcının bir eseri okutan alt süreci
"""
from __future__ import annotations

import argparse
import sys
from typing import Callable

from .yollar import Yollar


def _durum(y: Yollar, _a: argparse.Namespace) -> int:
    from .durum import DurumDeposu
    from .hazirlik import kuyruk, okunacak_mi
    from .katalog import Katalog
    from .kontrol import KontrolSonucu
    from .teslim import gecerli_teslim

    k = Katalog.yukle(y)
    d = DurumDeposu(y.durum).oku()
    print(f"{'No':>3}  {'Eser':<42} Durum")
    for e in sorted(k.etkinler(), key=lambda e: e.no):
        t = gecerli_teslim(e, y)
        if t:
            durum = f"teslim edildi ({t.parent.name})"
        elif not okunacak_mi(e, y):
            durum = "okunmayacak (Emel'li kopyası yok, yalniz_fola değil)"
        elif e.ad in d.atama:
            durum = f"okunuyor: {d.atama[e.ad]}" + (f" + {', '.join(d.ortaklar(e.ad))}" if d.ortaklar(e.ad) else "")
        else:
            durum = "sırada"
        kontrol = KontrolSonucu.oku(y.fola_klasoru(e.ad))
        if not t and kontrol:
            durum += f"; kontrol %{kontrol.eslesme:.2f} {'geçti' if kontrol.gecti else 'GEÇMEDİ'}"
        print(f"{e.no:>3}  {e.eser[:42]:<42} {durum}")
    print("\nKuyruk (kısadan uzuna):", ", ".join(f"{i.ad} ({i.uzunluk:,} kr)" for i in kuyruk(k, y)) or "boş")
    from .kota import kota_gunu
    from .olcum import BOSA_GIDEN, istek_ozeti
    gun = kota_gunu()
    o = istek_ozeti(y.istek_defteri, gun)
    harcanan = o.get("ses", 0) + sum(o.get(x, 0) for x in BOSA_GIDEN)
    bosa = harcanan - o.get("ses", 0)
    print(f"\nBugünkü istekler (kota günü {gun}): {harcanan} kota harcayan istek, {o.get('ses', 0)} ses geldi, "
          f"{bosa} boşa gitti" + (f" (%{100 * bosa / harcanan:.0f})" if harcanan else "")
          + (f"; ayrıntı: {', '.join(f'{k} {v}' for k, v in sorted(o.items()))}" if o else ""))
    return 0


def _oku(y: Yollar, a: argparse.Namespace) -> int:
    from .kilit import ZatenCalisiyor, tek_kopya
    from .zamanlayici import ARACLAR, kur
    kotalar = {ARACLAR[0].model: a.lite, ARACLAR[1].model: a.flash, ARACLAR[2].model: a.k31}
    try:
        with tek_kopya(y.zamanlayici_kilidi):  # iki kopya aynı eseri aynı anda okuyup kotayı iki kez yakmasın
            kur(y, kotalar).calis()
    except ZatenCalisiyor as h:
        print(f"okuma programı zaten çalışıyor; ikinci kopya başlatılmadı ({h})")
        return 1
    return 0


def _oku_eser(y: Yollar, a: argparse.Namespace) -> int:
    from .isci import IsTanimi, oku_eser
    is_ = IsTanimi(ad=a.ad, arac_adi=a.arac_adi, model=a.model, ses=a.ses,
                   ortak=tuple(m for m in (a.ortak or "").split(",") if m), hedef_sn=a.hedef_sn,
                   sabit_blok=a.sabit_blok)
    return int(oku_eser(is_, y))


def _kontrol(y: Yollar, a: argparse.Namespace) -> int:
    from .kontrol import kontrol_et
    s = kontrol_et(y.fola_klasoru(a.ad), y.parcalar)
    print(s.ozet().split("\n\n", 1)[-1] if s.bloklar else "blok yok")
    return 0 if s.gecti else 1


def _teslim(y: Yollar, a: argparse.Namespace) -> int:
    from .katalog import Katalog
    from .teslim import TeslimDurumu, teslim_et
    k = Katalog.yukle(y)
    eserler = [k.al(a.ad)] if a.ad else k.etkinler()
    hata = 0
    for e in eserler:
        s = teslim_et(e, y)
        if s.durum is TeslimDurumu.KONULDU and s.hedef is not None:
            print(f"konuldu: {s.hedef.parent.name}/{s.hedef.name} (eşleşme %{s.eslesme:.2f})")
            for c in s.cope:
                print(f"eski hâli Çöp Sepeti'ne kondu: {c.name}")
        elif a.ad or s.durum not in (TeslimDurumu.GUNCEL, TeslimDurumu.KAYIT_YOK):
            print(f"{e.dosya_adi}: {s.durum.value}")
            hata += s.durum is not TeslimDurumu.GUNCEL
    return 1 if hata else 0


def _ceviri(y: Yollar, a: argparse.Namespace) -> int:
    from . import ceviri
    paragraf, kelime = ceviri.yaz(a.ad, y)
    ses = y.eser_klasoru(a.ad) / "seslendirme-metni.txt"
    print(f"paragraf: {paragraf} | kelime: {kelime:,}")
    kalan = ceviri.okunussuz_adlar(ses.read_text(encoding="utf-8"))
    if kalan:
        print("okunuşu yazılmamış olabilecek adlar:", ", ".join(kalan[:60]))
    return 0


def _hazirla(y: Yollar, a: argparse.Namespace) -> int:
    from .hazirlik import metni_hazirla
    from .katalog import Katalog
    print(metni_hazirla(Katalog.yukle(y).al(a.ad), y))
    return 0


def _site(y: Yollar, a: argparse.Namespace) -> int:
    from . import site
    katalog, yakinda = site.hazirla(y, kuru=a.kuru)
    if a.kuru:
        print(f"{len(katalog)} eser yayında olurdu; Yakında: {', '.join(x['id'] for x in yakinda['yakinda']) or 'boş'}")
    return 0


def ayristirici() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="sesli_kitap.py", description="Sesli kitap üretim sistemi")
    alt = ap.add_subparsers(dest="komut", required=True, metavar="komut")

    alt.add_parser("durum", help="eserlerin ve okumanın durumu").set_defaults(is_=_durum)

    p = alt.add_parser("oku", help="zamanlayıcıyı başlatır")
    for ad, yardim in (("lite", "3.8 Flash Lite"), ("flash", "3.8 Flash"), ("k31", "3.1 Flash")):
        p.add_argument(f"--{ad}", type=int, default=10, help=f"{yardim} günlük istek hakkı (0: kullanma)")
    p.set_defaults(is_=_oku)

    p = alt.add_parser("oku-eser", help="(iç kullanım) bir eseri okutan alt süreç")
    p.add_argument("ad")
    p.add_argument("--arac-adi", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--ses", required=True)
    p.add_argument("--ortak")
    plan = p.add_mutually_exclusive_group(required=True)
    plan.add_argument("--hedef-sn", type=int)
    plan.add_argument("--sabit-blok", type=int)
    p.set_defaults(is_=_oku_eser)

    for ad, is_, yardim in (("kontrol", _kontrol, "okunmuş eseri yeniden kontrol eder"),
                            ("ceviri", _ceviri, "çeviri bölümlerini birleştirir"),
                            ("hazirla", _hazirla, "okuma metnini günceller")):
        p = alt.add_parser(ad, help=yardim)
        p.add_argument("ad")
        p.set_defaults(is_=is_)

    p = alt.add_parser("teslim", help="kontrolden geçen okumaları teslim eder")
    p.add_argument("ad", nargs="?")
    p.set_defaults(is_=_teslim)

    p = alt.add_parser("site", help="site yayın klasörünü hazırlar")
    p.add_argument("--kuru", action="store_true", help="hiçbir şey yazmadan sonucu göster")
    p.set_defaults(is_=_site)
    return ap


def main(argv: list[str] | None = None, yollar: Yollar | None = None) -> int:
    a = ayristirici().parse_args(argv)
    komut: Callable[[Yollar, argparse.Namespace], int] = a.is_
    return komut(yollar or Yollar.varsayilan(), a)


if __name__ == "__main__":
    sys.exit(main())
