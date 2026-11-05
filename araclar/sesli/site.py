""""Melih'ten Dinle" sitesinin yayın klasörünü (~/Library/Caches/melihten-dinle/yayin) hazırlar.

Kaynak: teslim klasörünün araç alt klasörleri (yalnız kontrolden geçmiş TTS kayıtları; Live ve 2.5 hariç).
- Site kopyası 64 kbps (yükleme ve aylık aktarım kotası yarıya iner; konuşmada fark duyulmaz).
- Netlify 10 MB'tan büyük dosyaları iyi sunmuyor: her MP3 çerçeve sınırlarından ≤ 9 MiB'lik eşit parçalara bölünür,
  oynatıcı parçaları tek kayıt gibi çalar. Parça klasörünün adında kaynağın özeti var (ses/<eser>-<özet>/): eser
  değişirse adres de değişir, tarayıcı eski parçayı önbellekten çalmaz.
- katalog.json (eserler), yakinda.json (okuma kuyruğu + "Eser iste" WhatsApp numarası) yazılır.
- Yayın klasörü yalnız bu modülce yazılır; ses parçaları kaynak değişmedikçe yeniden kodlanmaz.

Yayına alma (deploy) bu modülün işi değildir: her seferinde kullanıcının açık onayıyla elle yapılır.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import shutil
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections.abc import Callable

from .ayar import env_oku
from .durum import DurumDeposu
from .hazirlik import kuyruk
from .katalog import Katalog, KatalogHatasi
from .teslim import YENILENECEK
from .yollar import Yollar
import lameenc
import soundfile as sf

Plan = dict[int, dict[str, str]]  # yol haritası CSV'si: eser no → sütunlar (Köken, Ülke, …)

PARCA_SINIRI = 9 * 2**20
NETLIFY_SINIRI = 10 * 2**20
KBPS = 64
ESZAMANLI = 4  # 8 GB bellekte güvenli kodlama süreci sayısı
SURE_TOLERANSI = 0.5  # sn; parçaların toplamı kaynaktan bu kadar sapabilir
# MP3 çerçeve başlığı (ISO 11172-3): senkron bitleri, MPEG-1 sürüm kodu, ayrılmış örnekleme kodu, tek kanal kodu
SENK, SENK_MASKE, MPEG1, AYRILMIS_ORNEK, TEK_KANAL = 0xFF, 0xE0, 3, 3, 3

# MPEG ses çerçevesi başlığı tabloları (Layer III)
_BIT = {1: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
        2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]}
_ORNEK = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


class SiteHatasi(RuntimeError):
    pass


@dataclass(frozen=True)
class Cerceve:
    bas: int
    uzunluk: int
    ornek: int
    hz: int


def cerceveler(veri: bytes) -> list[Cerceve]:
    """MP3 ses çerçeveleri. ID3 etiketleri ve çöp baytlar atlanır; Xing/Info (VBR başlığı) çerçevesi de atlanır,
    yoksa tarayıcı ilk parçanın süresini bütün eserin süresi sanır."""
    i, n, sonuc = 0, len(veri), []
    while i + 4 <= n:
        if veri[i:i + 3] == b"ID3" and i + 10 <= n:
            boy = (veri[i + 6] << 21) | (veri[i + 7] << 14) | (veri[i + 8] << 7) | veri[i + 9]
            i += 10 + boy + (10 if veri[i + 5] & 0x10 else 0)
            continue
        if veri[i:i + 3] == b"TAG":  # ID3v1 (dosya sonu)
            i += 128
            continue
        b1, b2 = veri[i + 1], veri[i + 2]
        if veri[i] != SENK or (b1 & SENK_MASKE) != SENK_MASKE or (b1 >> 1) & 3 != 1:
            i += 1
            continue
        surum = (b1 >> 3) & 3  # 3: MPEG-1, 2: MPEG-2, 0: MPEG-2.5
        bi, si, dolgu = b2 >> 4, (b2 >> 2) & 3, (b2 >> 1) & 1
        if surum == 1 or bi in (0, 15) or si == AYRILMIS_ORNEK:
            i += 1
            continue
        hz = _ORNEK[surum][si]
        bit = _BIT[1 if surum == MPEG1 else 2][bi] * 1000
        uzun = (144 if surum == MPEG1 else 72) * bit // hz + dolgu
        if i + uzun > n:
            break
        tek = (veri[i + 3] >> 6) == TEK_KANAL
        yan = (17 if tek else 32) if surum == MPEG1 else (9 if tek else 17)
        if veri[i + 4 + yan:i + 8 + yan] not in (b"Xing", b"Info"):
            sonuc.append(Cerceve(i, uzun, 1152 if surum == MPEG1 else 576, hz))
        i += uzun
    return sonuc


def kodla(mp3: Path, kbps: int = KBPS) -> tuple[bytes, float]:
    """MP3'ü akış hâlinde açıp yeniden kodlar (6,8 saatlik eser belleğe sığmaz); (baytlar, saniye)."""
    bilgi = sf.info(str(mp3))
    e = lameenc.Encoder()
    e.set_bit_rate(kbps)
    e.set_in_sample_rate(bilgi.samplerate)
    e.set_channels(1)
    e.set_quality(5)  # 2'ye göre 3 kat hızlı; konuşmada fark duyulmaz
    cikti, ornek = bytearray(), 0
    for blok in sf.blocks(str(mp3), blocksize=bilgi.samplerate * 300, dtype="int16", always_2d=True):
        cikti += e.encode(blok[:, 0].tobytes())
        ornek += len(blok)
    cikti += e.flush()
    return bytes(cikti), ornek / bilgi.samplerate


def bol(veri: bytes, hedef: Path, sinir: int = PARCA_SINIRI) -> list[float]:
    """MP3 baytlarını sınırı aşmayan eşit parçalara (1.mp3, 2.mp3 …) böler; parça sürelerini döndürür."""
    cer = cerceveler(veri)
    if not cer:
        raise SiteHatasi("MP3 çerçevesi bulunamadı")
    if max(c.uzunluk for c in cer) > sinir:
        raise SiteHatasi("tek çerçeve parça sınırından büyük")
    # eşit çerçeve sayılı parçalar; çerçeve boyları az da olsa değiştiği için bir parça sınırı aşarsa adet artırılır
    adet = -(-sum(c.uzunluk for c in cer) // sinir)
    while True:
        boy = -(-len(cer) // adet)
        gruplar = [cer[p * boy:(p + 1) * boy] for p in range(adet)]
        if all(sum(c.uzunluk for c in g) <= sinir for g in gruplar):
            break
        adet += 1
    hedef.mkdir(parents=True)
    sureler = []
    for p, grup in enumerate(g for g in gruplar if g):
        (hedef / f"{p + 1}.mp3").write_bytes(b"".join(veri[c.bas:c.bas + c.uzunluk] for c in grup))
        sureler.append(round(sum(c.ornek / c.hz for c in grup), 3))
    return sureler


def parcala(mp3: Path, klasor: Path) -> str:
    """Bir eseri kodlayıp böler, bilgi.json'u en son yazar (yarıda kalan klasör bilgi.json'suz kalır). Ayrı süreçte
    çalışır."""
    veri, saniye = kodla(mp3)
    sureler = bol(veri, klasor)
    # süre kaynağın süresini tutmalı (kodlayıcı başa/sona birkaç ms ekler): parça kaybı varsa yayın yapılmasın
    if abs(sum(sureler) - saniye) > SURE_TOLERANSI:
        shutil.rmtree(klasor)
        raise SiteHatasi(f"parçaların süresi tutmuyor: {mp3.name} {sum(sureler):.1f} != {saniye:.1f}")
    (klasor / "bilgi.json").write_text(json.dumps({"sureler": sureler, "boyut": len(veri)}))
    return f"{KBPS} kbps, bölündü: {mp3.name} → {len(sureler)} parça"


@dataclass(frozen=True)
class YayinEseri:
    mp3: Path
    ad: str
    klasor: Path  # yayin/ses/<ad>-<özet>


class OzetOnbellegi:
    """Kaynak MP3'lerin içerik özetleri; dosya (yol, boyut, değişme zamanı) değişmedikçe yeniden okunmaz. Teslim
    klasörü iCloud'da: okumak her seferinde gigabaytlarca indirme demekti. Yayın klasörünün dışında durur."""

    def __init__(self, dosya: Path):
        self.dosya = dosya
        try:
            self._veri: dict[str, str] = json.loads(dosya.read_text())
        except (OSError, ValueError):
            self._veri = {}

    def ozet(self, mp3: Path) -> str:
        st = mp3.stat()
        anahtar = f"{mp3}|{st.st_size}|{st.st_mtime_ns}|{KBPS}|{PARCA_SINIRI}"
        if anahtar not in self._veri:
            h = hashlib.sha1(usedforsecurity=False)  # dosya parmak izi: güvenlik amaçlı değil
            with open(mp3, "rb") as f:
                for parca in iter(lambda: f.read(2**22), b""):
                    h.update(parca)
            h.update(f"|{KBPS}|{PARCA_SINIRI}".encode())
            self._veri[anahtar] = h.hexdigest()[:8]
            self.dosya.parent.mkdir(parents=True, exist_ok=True)
            _json_yaz(self.dosya, self._veri)
        return self._veri[anahtar]


def yayin_eserleri(katalog: Katalog, yollar: Yollar, bildir: Callable[[str], None]) -> list[YayinEseri]:
    sonuc = []
    ozetler = OzetOnbellegi(yollar.yayin.parent / "ozetler.json")
    adaylar = (p for p in yollar.teslim.glob("*/*.mp3") if p.parent.name not in YENILENECEK)
    for mp3 in sorted(adaylar, key=lambda p: int(p.name.split(" - ")[0])):
        eser = katalog.numarayla(int(mp3.name.split(" - ")[0]))
        if eser is None:
            raise KatalogHatasi(f"eser listesinde karşılığı yok: {mp3.name}")
        if not eser.etkin:
            bildir(f"siteye alınmadı ({eser.durum.value}): {mp3.name}")
            continue
        sonuc.append(YayinEseri(mp3, eser.ad, yollar.yayin / "ses" / f"{eser.ad}-{ozetler.ozet(mp3)}"))
    return sonuc


def katalog_kaydi(e: YayinEseri, katalog: Katalog, plan: Plan, tanitim: dict[str, dict[str, str]]) -> dict[str, Any]:
    eser = katalog.al(e.ad)
    b = json.loads((e.klasor / "bilgi.json").read_text())
    p = plan.get(eser.no, {})
    arac = e.mp3.parent.name
    return {"id": eser.ad, "yol": f"/ses/{e.klasor.name}", "no": eser.no, "eser": eser.eser, "yazar": eser.yazar,
            "koken": p.get("Köken", ""), "ulke": p.get("Ülke", ""), "sure": round(sum(b["sureler"])),
            "boyut": b["boyut"], "parcalar": b["sureler"],
            "ses": "Sulafat" if "2.5" in arac or "3.1" in arac else "Fola",
            "tanitim": tanitim["eser"].get(eser.ad, ""), "yazarBilgi": tanitim["yazar"].get(eser.yazar, ""),
            "eklenme": dt.datetime.fromtimestamp(e.mp3.stat().st_mtime).strftime("%Y-%m-%dT%H:%M")}


def yakinda_listesi(katalog: Katalog, yollar: Yollar, plan: Plan) -> list[dict[str, Any]]:
    """"Yakında" rafı: okuma kuyruğundaki eserler, okunmakta olan önce."""
    atama = DurumDeposu(yollar.durum).oku().atama
    liste = []
    for i in kuyruk(katalog, yollar):
        p = plan.get(i.eser.no, {})
        liste.append({"id": i.ad, "no": i.eser.no, "eser": i.eser.eser, "yazar": i.eser.yazar,
                      "ulke": p.get("Ülke", ""), "koken": p.get("Köken", ""), "okunuyor": i.ad in atama})
    liste.sort(key=lambda x: not x["okunuyor"])
    return liste


def _plan(yollar: Yollar) -> Plan:
    with open(yollar.plan_csv, encoding="utf-8-sig") as f:
        return {int(s["No"]): s for s in csv.DictReader(f)}


def _json_yaz(yol: Path, veri: object) -> None:
    gecici = yol.with_name(yol.name + ".yaziliyor")
    gecici.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
    gecici.replace(yol)


def _site_dosyalarini_kopyala(yollar: Yollar) -> None:
    """Site dosyaları her seferinde baştan kopyalanır; ses parçaları (ses/) yerinde kalır."""
    yollar.yayin.mkdir(parents=True, exist_ok=True)
    (yollar.yayin / "ses").mkdir(exist_ok=True)
    for eski in yollar.yayin.iterdir():
        if eski.name != "ses":
            shutil.rmtree(eski) if eski.is_dir() else eski.unlink()
    for dosya in (yollar.kitaplik / "public").iterdir():
        if dosya.name == ".DS_Store":
            continue
        hedef = yollar.yayin / dosya.name
        shutil.copytree(dosya, hedef) if dosya.is_dir() else shutil.copy2(dosya, hedef)


def _eksik_sesleri_kodla(eserler: list[YayinEseri], bildir: Callable[[str], None]) -> None:
    """Parçaları hazır olmayan (bilgi.json'u olmayan) eserleri baştan kodlar."""
    eksik = [e for e in eserler if not (e.klasor / "bilgi.json").exists()]
    for e in eksik:
        shutil.rmtree(e.klasor, ignore_errors=True)
    if eksik:
        with ProcessPoolExecutor(ESZAMANLI) as havuz:
            for satir in havuz.map(parcala, [e.mp3 for e in eksik], [e.klasor for e in eksik]):
                bildir(satir)


def _eski_parcalari_cikar(yollar: Yollar, gecerli: set[str], bildir: Callable[[str], None]) -> None:
    """Katalogdan çıkan ya da değişen eserin eski parçaları yayından silinir."""
    for klasor in (yollar.yayin / "ses").iterdir():
        if klasor.name not in gecerli:
            shutil.rmtree(klasor)
            bildir(f"yayından çıkarıldı: {klasor.name}")


def hazirla(yollar: Yollar, bildir: Callable[[str], None] = print,
            kuru: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Yayın klasörünü günceller. kuru=True: hiçbir şey yazmaz, yalnız katalog ve yakında içeriğini hesaplar (ses
    parçaları zaten hazır olmalı)."""
    katalog = Katalog.yukle(yollar)
    plan = _plan(yollar)
    eserler = yayin_eserleri(katalog, yollar, bildir)

    if not kuru:
        _site_dosyalarini_kopyala(yollar)
        _eksik_sesleri_kodla(eserler, bildir)

    tanitim = json.loads((yollar.kitaplik / "tanitim.json").read_text(encoding="utf-8"))
    eksik_bilgi = [e.mp3.name for e in eserler if not (e.klasor / "bilgi.json").exists()]
    if eksik_bilgi and not kuru:
        raise SiteHatasi(f"ses parçaları hazır değil: {eksik_bilgi}")
    for ad in eksik_bilgi:  # kuru çalışmada kodlama yapılmaz: bu eserler gerçek hazırlıkta eklenir
        bildir(f"kodlanacak (önizlemede yok): {ad}")
    eserler = [e for e in eserler if (e.klasor / "bilgi.json").exists()]
    katalog_json = [katalog_kaydi(e, katalog, plan, tanitim) for e in eserler]
    yakinda = {"yakinda": yakinda_listesi(katalog, yollar, plan),
               "whatsapp": env_oku(yollar.kitaplik / ".env").get("WHATSAPP", "").strip()}
    if kuru:
        return katalog_json, yakinda

    _eski_parcalari_cikar(yollar, {e.klasor.name for e in eserler}, bildir)
    _json_yaz(yollar.yayin / "katalog.json", katalog_json)
    _json_yaz(yollar.yayin / "yakinda.json", yakinda)
    buyuk = [p for p in (yollar.yayin / "ses").rglob("*.mp3") if p.stat().st_size > NETLIFY_SINIRI]
    if buyuk:
        raise SiteHatasi(f"10 MB'ı aşan parça var: {buyuk}")
    bildir(f"{len(yakinda['yakinda'])} eser Yakında rafında")
    toplam = sum(k["boyut"] for k in katalog_json)
    bildir(f"{len(katalog_json)} eser, {sum(len(k['parcalar']) for k in katalog_json)} parça, "
           f"{round(sum(k['sure'] for k in katalog_json) / 3600, 1)} saat, {toplam / 1e9:.2f} GB → {yollar.yayin}")
    return katalog_json, yakinda
