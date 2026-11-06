"""Gerçek kayıtların denetimi: okuma günlüğü ve istek defteri "aynı iş iki kez yapıldı mı, emek kayboldu mu?"

Testler ancak düşünülen durumu sınar; bu betik gerçekte ne olduğuna bakar (kalite/HATA-DEFTERI.md H-001: kanıt
günlükte vardı, bakılmadı). Her çalıştırmada yalnız son denetimden bu yana eklenen satırlara bakar; konumu
.tmp/denetim-durumu.json'da tutar. Rapor notlar/denetim/<tarih>.md'ye eklenir (aynı gün üzerine yazılmaz). Alarm varsa çıkış kodu 1.

Kullanım:  .venv-ses/bin/python araclar/haftalik_denetim.py [--bastan]
  --bastan  kayıtlı konumu yok sayıp bütün günlüğü baştan denetler (geçmişe dönük tarama)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
GUNLUK = KOK / ".tmp" / "fola-sirayla.log"
DEFTER = KOK / ".tmp" / "istek-defteri.jsonl"
DURUM = KOK / ".tmp" / "denetim-durumu.json"
RAPOR = KOK / "notlar" / "denetim"
# okuma programının çalışırken açtığı yerler: biri yalnız iCloud'daysa program uyarısız takılır (H-016)
ORTAM = (".venv-ses", ".cache/python", ".cache/huggingface", "araclar")
SF_DATALESS = 0x40000000  # macOS: içeriği Mac'te olmayan, yalnız iCloud'da duran dosya (sys/stat.h)

BOSA_ORAN_SINIRI = 0.15   # kota harcayan isteklerin bundan fazlası ses getirmediyse alarm
EN_COK_DENEME = 3         # bir blok kalite yüzünden en çok bu kadar okunur (sesli/okuma.py DENEME); fazlası tekrar işidir
ZAMAN = re.compile(r"^(\d{2}\.\d{2} \d{2}:\d{2}) ")
# yeniden atılan istek iletileri (eski koddakiler geçmiş günlükler için kalır); testler/test_haftalik_denetim.py
# okuma programının bugünkü iletileriyle karşılaştırır
TEKRAR = ("bağlanılamadı", "yanıt kayboldu", "yanıt gecikiyor", "bağlantı koptu ya da zaman aşımı", "sunucu hatası, tekrar")
YARIM_DENEME = ("(deneme ", "ATLAMA", "SES BOZULUYOR")   # bloğun henüz diske yazılmamış okuması
KESINTI = ("KOTA_DOLDU", "GEÇİCİ SORUN", "Traceback")


@dataclass
class Bulgu:
    alarm: bool
    baslik: str
    ayrinti: list[str] = field(default_factory=list)


def _satirlar(yol: Path, konum: int) -> tuple[list[str], int]:
    if not yol.exists():
        return [], 0
    boy = yol.stat().st_size
    if konum > boy:  # dosya küçülmüş (yenilenmiş): baştan
        konum = 0
    with open(yol, "rb") as f:
        f.seek(konum)
        veri = f.read()
    return veri.decode("utf-8", errors="replace").splitlines(), konum + len(veri)


def gunlugu_denetle(satirlar: list[str]) -> list[Bulgu]:
    son_zaman = "?"
    tekrar: list[str] = []
    kayip: list[str] = []
    cokme: list[str] = []
    birakilan: list[str] = []
    onceki = ""
    for satir in satirlar:
        satir = satir.strip()
        if not satir or satir.startswith("Fetching"):
            continue
        if m := ZAMAN.match(satir):
            son_zaman = m[1]
        if any(t in satir for t in TEKRAR):
            tekrar.append(f"{son_zaman} {satir[:110]}")
        if any(k in satir for k in KESINTI) and any(y in onceki for y in YARIM_DENEME):
            kayip.append(f"{son_zaman} okunmuş ama kaydedilmemiş deneme kesintiye uğradı: {onceki[:90]}")
        if satir.startswith("Traceback"):
            cokme.append(f"{son_zaman} beklenmeyen hata")
        if "BIRAKILDI" in satir:
            birakilan.append(satir[:140])
        onceki = satir
    return [
        Bulgu(bool(kayip), f"Kaybolmuş olabilecek okuma: {len(kayip)}", kayip),
        Bulgu(len(tekrar) > 3, f"Yeniden atılan istek (zaman aşımı, kopma, sunucu): {len(tekrar)}", tekrar),
        Bulgu(bool(cokme), f"Beklenmeyen hata (Traceback): {len(cokme)}", cokme),
        Bulgu(False, f"Araçtan bırakılan eser: {len(birakilan)}", birakilan),
    ]


def _zaman(k: dict[str, object]) -> dt.datetime | None:
    try:
        return dt.datetime.strptime(str(k["zaman"]), "%Y-%m-%dT%H:%M:%S%z")
    except (KeyError, ValueError):
        return None


def defteri_denetle(satirlar: list[str]) -> list[Bulgu]:
    kayitlar = []
    for s in satirlar:
        try:
            kayitlar.append(json.loads(s))
        except ValueError:
            continue
    if not kayitlar:
        return [Bulgu(False, "İstek defteri: yeni kayıt yok")]
    sonuc: dict[str, int] = {}
    for k in kayitlar:
        sonuc[k.get("sonuc", "?")] = sonuc.get(k.get("sonuc", "?"), 0) + 1
    harcayan = len(kayitlar) - sonuc.get("gitmedi", 0) - sonuc.get("sinir", 0)
    bosa = harcayan - sonuc.get("ses", 0)
    oran = bosa / harcayan if harcayan else 0.0

    # aynı metin (özet) birden çok kez ses getirdiyse: kalite yüzünden yeniden okuma (en çok EN_COK_DENEME) olağandır,
    # fazlası aynı işin yeniden yaptırılmasıdır
    sesler: dict[str, int] = {}
    for k in kayitlar:
        if k.get("sonuc") == "ses":
            sesler[k["ozet"]] = sesler.get(k["ozet"], 0) + 1
    tekrar = [f"{o}: {n} kez" for o, n in sesler.items() if n > EN_COK_DENEME]
    yeniden = [f"{o}: {n} kez" for o, n in sesler.items() if 1 < n <= EN_COK_DENEME]

    # süreleri çakışan istekler: aynı anda birden fazla istek
    araliklar = sorted((z, z + dt.timedelta(seconds=float(k.get("sn", 0)))) for k in kayitlar if (z := _zaman(k)))
    cakisma = [f"{a[0]:%d.%m %H:%M:%S} ile {b[0]:%H:%M:%S}" for a, b in zip(araliklar, araliklar[1:]) if b[0] < a[1]]
    return [
        Bulgu(oran > BOSA_ORAN_SINIRI, f"Boşa giden istek: {bosa}/{harcayan} (%{100 * oran:.0f}); "
              f"ayrıntı: {', '.join(f'{k} {v}' for k, v in sorted(sonuc.items()))}"),
        Bulgu(bool(tekrar), f"Aynı metin {EN_COK_DENEME} kereden fazla seslendirildi: {len(tekrar)}", tekrar),
        Bulgu(False, f"Kalite yüzünden yeniden okunan blok (en çok {EN_COK_DENEME} deneme, olağan): {len(yeniden)}",
              yeniden),
        Bulgu(bool(cakisma), f"Aynı anda birden çok istek: {len(cakisma)}", cakisma),
    ]


def surecleri_denetle(cikti: str | None = None) -> list[Bulgu]:
    """Aynı anda birden çok okuma programı (zamanlayıcı) çalışıyor mu? `cikti`: `pgrep -fl` çıktısı (testler için)."""
    if cikti is None:
        cikti = subprocess.run(["pgrep", "-fl", "sesli_kitap.py oku"], capture_output=True, text=True,
                               check=False).stdout
    # alt süreç (oku-eser) ve programı uyutmayan sarmalayıcı (caffeinate) ikinci kopya değildir
    zamanlayici = [s for s in cikti.splitlines()
                   if len(s.split()) > 1 and "oku-eser" not in s and s.split()[1] != "caffeinate"]
    return [Bulgu(len(zamanlayici) > 1, f"Çalışan okuma programı kopyası: {len(zamanlayici)}", zamanlayici)]


def _bayrak(yol: str) -> tuple[int, int]:
    try:
        st = os.lstat(yol)
    except OSError:
        return 0, 0
    return getattr(st, "st_flags", 0), st.st_size


def ortami_denetle(kok: Path = KOK) -> list[Bulgu]:
    """Okuma ortamında yalnız iCloud'da duran dosya var mı? Dosyaları açmaz (açmak indirmeyi başlatıp takılırdı),
    yalnız işaretlerine bakar."""
    eksik: dict[str, list[int]] = {}
    for ad in ORTAM:
        for kl, _, dosyalar in os.walk(kok / ad):
            for d in dosyalar:
                bayrak, boy = _bayrak(os.path.join(kl, d))
                if bayrak & SF_DATALESS:
                    e = eksik.setdefault(ad, [0, 0])
                    e[0] += 1
                    e[1] += boy
    ayrinti = [f"{ad}: {n} dosya, {b / 1e9:.2f} GB yalnız iCloud'da" for ad, (n, b) in eksik.items()]
    if ayrinti:
        ayrinti.append("Çözüm: Finder'da klasöre sağ tıkla → \"İndirileni Tut\"")
    return [Bulgu(bool(eksik), f"Okuma ortamında Mac'te olmayan dosya: {sum(n for n, _ in eksik.values())}", ayrinti)]


def main(argv: list[str] | None = None) -> int:
    a = argparse.ArgumentParser(description="Gerçek kayıtların denetimi")
    a.add_argument("--bastan", action="store_true", help="bütün günlüğü baştan denetle")
    ayar = a.parse_args(argv)
    durum = {} if ayar.bastan or not DURUM.exists() else json.loads(DURUM.read_text())
    gunluk, g_konum = _satirlar(GUNLUK, int(durum.get("gunluk", 0)))
    defter, d_konum = _satirlar(DEFTER, int(durum.get("defter", 0)))
    bulgular = gunlugu_denetle(gunluk) + defteri_denetle(defter) + surecleri_denetle() + ortami_denetle()

    simdi = dt.datetime.now()
    alarm = [b for b in bulgular if b.alarm]
    yazi = [f"# Kayıt denetimi {simdi:%d.%m.%Y %H:%M}", "",
            f"Kapsam: okuma günlüğünün {len(gunluk)} yeni satırı, istek defterinin {len(defter)} yeni kaydı.", "",
            f"**{'ALARM: ' + str(len(alarm)) + ' bulgu' if alarm else 'Alarm yok'}**", ""]
    for b in bulgular:
        yazi.append(f"- {'⚠️ ' if b.alarm else ''}{b.baslik}")
        yazi += [f"  - {x}" for x in b.ayrinti[:15]] + ([f"  - … {len(b.ayrinti) - 15} tane daha"] if len(b.ayrinti) > 15 else [])
    RAPOR.mkdir(parents=True, exist_ok=True)
    rapor = RAPOR / f"{simdi:%Y-%m-%d}.md"
    with open(rapor, "a", encoding="utf-8") as f:  # gün içinde birden çok denetim: öncekinin bulguları kalır
        f.write(("\n---\n\n" if f.tell() else "") + "\n".join(yazi) + "\n")
    DURUM.write_text(json.dumps({"gunluk": g_konum, "defter": d_konum, "son": f"{simdi:%Y-%m-%d %H:%M}"}))
    print("\n".join(yazi))
    print(f"\nRapor: {rapor}")
    return 1 if alarm else 0


if __name__ == "__main__":
    sys.exit(main())
