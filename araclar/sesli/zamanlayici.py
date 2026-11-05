"""Eserleri kotalı Gemini TTS araçlarına dağıtıp sırayla okutan uzun ömürlü süreç.

Kurallar (kullanıcının 26 Ekim – 4 Kasım 2026 kararları):
- Bir eser baştan sona tek araçla (tek sesle) okunur; esere başlayan araç ona atanır. Kota eserin ortasında biterse
  ertesi gün aynı araç önbellekteki blokları atlayıp kaldığı yerden sürer. `ortak` ile işaretlenmiş araçlar da aynı
  eseri sürdürebilir (aynı ses, aynı blok planı).
- Araçlar kazanç sırasıyla çalışır (Lite en hızlı okuyan ve en az atlayan). Kotası olan araç, atanmış eseri yoksa
  sahipsiz eserlerden kendi payını alır; pay, araçların aşağı yukarı aynı gün bitireceği biçimde dağıtılır.
- Güvenlik filtresi ya da boş yanıt eseri o araçtan alır (`ret`), başka araç baştan okur. Bağlantı sorunu eserin
  suçu değildir: beklenip yeniden denenir. Beklenmeyen hata iki kez olursa eser araçtan alınır (kota döngüde yanmasın).
- Kontrolden geçmeyen okumada önce yalnız sorunlu bloklar aynı araçla yeniden okunur (bir kez); yine geçmezse eser
  araçtan alınır.
- Hiçbir aracın kotası kalmayınca kotanın yenilendiği ABD Pasifik gece yarısı +5 dk'ya kadar beklenir. Bekleme duvar
  saatine bakar (Mac uyurken time.sleep süresi işlemez).
- Bir araçta üst üste GECICI_SINIRI kez geçici sorun çıkarsa araç kota yenilenene dek dinlenir: süren bir kesinti
  her 10 dakikada yeni istek yakarak kotayı bitirmesin.
- Aynı anda tek zamanlayıcı çalışır (cli.py, kilit.tek_kopya); alt süreç de eser başına kilit alır.
"""
from __future__ import annotations

import datetime as dt
import json
import time
from dataclasses import dataclass, field
from typing import Callable

from . import olcum
from .durum import SABIT, UYARLAMALI, Durum, DurumDeposu
from .gemini import Arac
from .kota import KOTA_SAAT_DILIMI
from .hazirlik import KuyrukIsi, kuyruk
from .isci import Cikis, IsTanimi, calistir
from .katalog import Katalog
from .kontrol import KontrolSonucu
from .metin import SABIT_BLOK as SABIT_VARSAYILAN
from .teslim import TeslimDurumu, teslim_et
from .yollar import Yollar

GUNLUK_ISTEK = 10
VARSAYILAN_HEDEF = 570   # sn; ölçüm yokken bir isteğin hedef ses süresi
EN_UZUN_HEDEF = 1200
SABIT_KAPASITE = 25000   # kr/gün; sabit bloklu araç (3.1) için kaba tahmin
HATA_SINIRI = 2
HATA_BEKLEMESI = 600     # sn
GECICI_BEKLEMESI = 600   # sn
GECICI_SINIRI = 3        # üst üste bu kadar geçici sorunda araç kota yenilenene dek dinlenir
ONARIM_SINIRI = 1

# kazanç sırası (28 Ekim ölçümü). 3.1 uzun blokları güvenlikte reddediyor: kısa sabit blok, fırsat aracı.
ARACLAR = (
    Arac("Gemini 3.8 Flash Lite TTS", "gemini-3.8-flash-lite-tts", "Fola"),
    Arac("Gemini 3.8 Flash TTS", "gemini-3.8-flash-tts", "Fola"),
    Arac("Gemini 3.1 Flash TTS", "gemini-3.1-flash-tts-preview", "Sulafat", sabit_blok=2000),
)


@dataclass
class AracDurumu:
    arac: Arac
    gunluk: int               # günlük istek hakkı (0: park edilmiş araç, ertesi gün de iş almaz)
    kota_var: bool = True
    kapasite: float = 0.0     # günde okuyabileceği tahmini karakter
    gecici: int = 0           # üst üste geçici sorun sayısı

    @property
    def model(self) -> str:
        return self.arac.model


def _aile(model: str) -> str:
    return model.split("-tts")[0].rsplit("-", 2)[0]


def hedef_sn(model: str, yollar: Yollar) -> int:
    """Uyarlamalı planda bir isteğin hedef ses süresi. Asıl sınır isteğe sığan metin (≈20000 kr); 3.8 Lite 20132
    kr'yi 1233 sn'de tam okudu. Aynı ailenin (3.8 Flash ile Lite aynı aile) en uzun tam ölçümünden hesaplanır."""
    try:
        olculen = json.loads(yollar.sinir.read_text())
    except (OSError, ValueError):
        olculen = {}
    aile = [v for k, v in olculen.items()
            if _aile(k) == _aile(model) or (k.startswith("gemini-3.8") and model.startswith("gemini-3.8"))]
    tam = [v["sn"] for v in aile if v.get("durum") == "tam"]
    if tam:
        return int(min(max(max(tam) * 0.92, VARSAYILAN_HEDEF), EN_UZUN_HEDEF))
    kesik = [v["sn"] for v in aile if v.get("durum") == "kesik"]
    if kesik:
        return int(max(min(kesik) * 0.88, 470))
    return VARSAYILAN_HEDEF if not aile else 540


def kapasite(arac: Arac, yollar: Yollar) -> float:
    if arac.sabit_blok:
        return SABIT_KAPASITE
    basari = olcum.basari_orani(yollar.olcum, arac.model)
    return GUNLUK_ISTEK * hedef_sn(arac.model, yollar) * olcum.model_hizi(yollar.olcum, arac.model) * max(basari, 0.4)


def dagit(araclar: list[AracDurumu], durum: Durum, boy: dict[str, int]) -> dict[str, list[str]]:
    """Sahipsiz eserleri, araçlar aşağı yukarı aynı gün bitirecek biçimde paylaştırır (en uzun iş, o an en erken
    bitecek araca). Sabit bloklu araç pay almaz: kabul edeceği eser önceden bilinmiyor, kendi denemesiyle kapar."""
    yuk = {a.model: sum(boy[e] for e, m in durum.atama.items() if m == a.model and e in boy) / a.kapasite
           for a in araclar}
    plan: dict[str, list[str]] = {a.model: [] for a in araclar}
    for e in sorted((e for e in boy if e not in durum.atama), key=boy.__getitem__, reverse=True):
        uygun = [a for a in araclar if not a.arac.sabit_blok and not durum.reddedildi_mi(a.model, e)]
        if not uygun:
            continue
        a = min(uygun, key=lambda a: yuk[a.model] + boy[e] / a.kapasite)
        plan[a.model].append(e)
        yuk[a.model] += boy[e] / a.kapasite
    return plan


def sec(araclar: list[AracDurumu], durum: Durum, boy: dict[str, int]) -> tuple[AracDurumu, str] | None:
    """Sıradaki (araç, eser): önce aracın atanmış ya da ortak okuduğu eser, sonra öncelikli eser, sonra payı;
    payı yoksa dengeyi en çok bozan en uzun sahipsiz eser."""
    plan = dagit(araclar, durum, boy)
    for a in araclar:
        if not a.kota_var or a.gunluk <= 0:
            continue
        atanan = [e for e, m in durum.atama.items() if m == a.model]
        atanan += [e for e, ms in durum.ortak.items() if a.model in ms and e in boy and e not in atanan]
        if atanan:
            return a, atanan[0]
        if not a.arac.sabit_blok:
            onc = [e for e in durum.oncelik if e in boy and e not in durum.atama and not durum.reddedildi_mi(a.model, e)]
            if onc:
                return a, onc[0]
        pay = sorted(plan[a.model], key=boy.__getitem__)
        if not pay:
            pay = sorted((e for e in boy if e not in durum.atama and not durum.reddedildi_mi(a.model, e)),
                         key=boy.__getitem__, reverse=True)
        if pay:
            return a, pay[0]
    return None


def kota_yenilenme(simdi: dt.datetime) -> dt.datetime:
    """Kotanın yenileneceği an (yerel saat, saat dilimsiz): ABD Pasifik gece yarısından 5 dk sonra."""
    pasifik = simdi.astimezone(KOTA_SAAT_DILIMI)
    sonraki = pasifik.replace(hour=0, minute=5, second=0, microsecond=0) + dt.timedelta(days=1)
    return sonraki.astimezone().replace(tzinfo=None)


def duvar_saatiyle_bekle(bitis: dt.datetime, uyu: Callable[[float], None] = time.sleep,
                         simdi: Callable[[], dt.datetime] = dt.datetime.now) -> None:
    while simdi() < bitis:
        uyu(min(60.0, max(1.0, (bitis - simdi()).total_seconds())))


@dataclass
class Bagimliliklar:
    """Zamanlayıcının dış dünyası; testler sahteleriyle değiştirir."""
    katalog: Callable[[], Katalog]
    kuyruk: Callable[[Katalog], list[KuyrukIsi]]
    calistir: Callable[[IsTanimi], Cikis]
    teslim: Callable[[str], TeslimDurumu]
    sorunlu_dosyalari_sil: Callable[[str], int]
    bekle: Callable[[dt.datetime], None]
    simdi: Callable[[], dt.datetime]
    kayit: Callable[[str], None]
    hedef_sn: Callable[[str], int]


def gercek_bagimliliklar(yollar: Yollar) -> Bagimliliklar:
    def kayit(s: str) -> None:
        print(dt.datetime.now().strftime("%d.%m %H:%M"), s, flush=True)

    def teslim(ad: str) -> TeslimDurumu:
        sonuc = teslim_et(Katalog.yukle(yollar).al(ad), yollar)
        if sonuc.durum is TeslimDurumu.KONULDU and sonuc.hedef:
            kayit(f"konuldu: {sonuc.hedef.parent.name}/{sonuc.hedef.name} (eşleşme %{sonuc.eslesme:.2f})")
            for c in sonuc.cope:
                kayit(f"eski hâli Çöp Sepeti'ne kondu: {c.name}")
        return sonuc.durum

    return Bagimliliklar(
        katalog=lambda: Katalog.yukle(yollar), kuyruk=lambda k: kuyruk(k, yollar, hazirla=True, uyar=kayit),
        calistir=lambda is_: calistir(is_, yollar),
        teslim=teslim, sorunlu_dosyalari_sil=lambda ad: sorunlu_bloklari_sil(ad, yollar),
        bekle=duvar_saatiyle_bekle, simdi=dt.datetime.now, kayit=kayit, hedef_sn=lambda m: hedef_sn(m, yollar))


def sorunlu_bloklari_sil(ad: str, yollar: Yollar) -> int:
    """Kontrolde atlama ya da 0,90 altı eşleşme, ses ölçümünde bozulma çıkan blokların önbellek dosyalarını siler
    (gerisi kalır): yeniden çalıştırınca yalnız onlar okunur. Silinen dosya sayısını döndürür."""
    fola = yollar.fola_klasoru(ad)
    try:
        plan = {p["no"]: p["dosya"] for p in json.loads((fola / "plan.json").read_text(encoding="utf-8"))
                if p.get("dosya")}
    except (OSError, ValueError):
        return 0
    kontrol = KontrolSonucu.oku(fola)
    sorunlu = set(kontrol.sorunlu_bloklar()) if kontrol else set()
    try:
        sorunlu |= {k["no"] for k in json.loads((fola / "kalite.json").read_text(encoding="utf-8")) if k["bozuk"]}
    except (OSError, ValueError, KeyError):
        pass
    n = 0
    for no in sorted(sorunlu):
        if no in plan and (d := yollar.parcalar / plan[no]).exists():
            d.unlink()
            n += 1
    return n


@dataclass
class Zamanlayici:
    depo: DurumDeposu
    b: Bagimliliklar
    araclar: list[AracDurumu]
    hata: dict[str, int] = field(default_factory=dict)

    def calis(self, tur_siniri: int | None = None) -> None:
        """Kuyruk bitene dek okur. tur_siniri yalnız testler içindir."""
        tur = 0
        while tur_siniri is None or tur < tur_siniri:
            tur += 1
            if not self.adim():
                return

    def adim(self) -> bool:
        """Bir iş yapar ya da kota yenilenene dek bekler; kuyruk bittiyse False."""
        isler = self.b.kuyruk(self.b.katalog())
        if not isler:
            self.b.kayit("HEPSİ BİTTİ")
            return False
        boy = {i.ad: i.uzunluk for i in isler}
        with self.depo.degistir() as d:
            d.atama = {e: m for e, m in d.atama.items() if e in boy}
            secim = sec(self.araclar, d, boy)
            is_ = self._ata(d, *secim) if secim else None
        if secim is None or is_ is None:
            self._kotayi_bekle()
            return True
        a = secim[0]
        isim = next(i.eser.dosya_adi for i in isler if i.ad == is_.ad)
        plan = f"hedef {is_.hedef_sn} sn/istek" if is_.hedef_sn else f"{is_.sabit_blok} kr'lik bloklar"
        self.b.kayit(f"BAŞLADI {isim} — {a.arac.ad} ({a.arac.ses}), {plan}")
        self._sonuc(a, is_.ad, isim, self.b.calistir(is_))
        return True

    def _ata(self, d: Durum, a: AracDurumu, ad: str) -> IsTanimi:
        """Eseri araca atar (durum kilidi altında çağrılır) ve okuma işini tanımlar."""
        if ad not in d.atama:  # yeni başlayan eser; yarım kalanlar kendi planıyla biter
            d.yontem[ad] = SABIT if a.arac.sabit_blok else UYARLAMALI
        if a.model not in d.ortaklar(ad):  # ortak okunan eserin ilk aracı ataması korunur
            d.atama[ad] = a.model
        ortak = tuple(m for m in [*d.ortaklar(ad), d.atama.get(ad, "")] if m and m != a.model)
        uyarlamali = d.yontem.get(ad) == UYARLAMALI
        return IsTanimi(ad=ad, arac_adi=a.arac.ad, model=a.model, ses=a.arac.ses, ortak=ortak,
                        hedef_sn=self.b.hedef_sn(a.model) if uyarlamali else None,
                        sabit_blok=None if uyarlamali else (a.arac.sabit_blok or SABIT_VARSAYILAN))

    def _kotayi_bekle(self) -> None:
        bitis = kota_yenilenme(self.b.simdi())
        self.b.kayit(f"bugün araçların okuyabileceği iş kalmadı (kota bitti ya da kalan eserleri okuyamıyor); "
                     f"{bitis:%d.%m %H:%M}'e kadar bekleniyor")
        self.b.bekle(bitis)
        for x in self.araclar:
            x.kota_var = True
            x.gecici = 0

    def _birak(self, a: AracDurumu, ad: str, isim: str, neden: str) -> None:
        with self.depo.degistir() as d:
            d.reddet(a.model, ad)
        self.b.kayit(f"BIRAKILDI {isim} — {a.arac.ad}: {neden}; başka araçla baştan okunacak")

    def _sonuc(self, a: AracDurumu, ad: str, isim: str, cikis: Cikis) -> None:
        a.gecici = a.gecici + 1 if cikis is Cikis.GECICI else 0
        if cikis is Cikis.KOTA:
            a.kota_var = False
            self.b.kayit(f"{a.arac.ad} kotası doldu; {isim} yarın aynı araçla kaldığı yerden sürecek")
        elif cikis is Cikis.GUVENLIK:
            self._birak(a, ad, isim, "güvenlik filtresi reddetti")
        elif cikis is Cikis.BOLUNEMEZ:
            self._birak(a, ad, isim, "model boş yanıt veriyor")
        elif cikis is Cikis.GECICI and a.gecici >= GECICI_SINIRI:
            a.kota_var = False
            self.b.kayit(f"GEÇİCİ SORUN {a.gecici} kez üst üste: {a.arac.ad} kota yenilenene dek dinleniyor "
                         f"(kota boşa yanmasın); {isim} kaldığı yerden sürecek")
        elif cikis is Cikis.GECICI:
            self.b.kayit(f"GEÇİCİ SORUN: {isim}; {GECICI_BEKLEMESI // 60} dk sonra yeniden denenecek")
            self.b.bekle(self.b.simdi() + dt.timedelta(seconds=GECICI_BEKLEMESI))
        elif cikis is Cikis.HATA:
            self.hata[ad] = self.hata.get(ad, 0) + 1
            if self.hata[ad] >= HATA_SINIRI:
                self._birak(a, ad, isim, f"{HATA_SINIRI} kez beklenmeyen hata")
            else:
                self.b.kayit(f"HATA: {isim}; {HATA_BEKLEMESI // 60} dk sonra yeniden denenecek")
                self.b.bekle(self.b.simdi() + dt.timedelta(seconds=HATA_BEKLEMESI))
        else:
            self._teslim(a, ad, isim)

    def _teslim(self, a: AracDurumu, ad: str, isim: str) -> None:
        sonuc = self.b.teslim(ad)
        if sonuc in (TeslimDurumu.KONULDU, TeslimDurumu.GUNCEL):
            with self.depo.degistir() as d:
                d.bitir(ad)
            self.b.kayit(f"BİTTİ {isim} — {a.arac.ad} ({a.arac.ses})")
            return
        with self.depo.degistir() as d:
            deneme = d.onarim.get(ad, 0)
            if deneme < ONARIM_SINIRI:
                d.onarim[ad] = deneme + 1
        if deneme < ONARIM_SINIRI and (n := self.b.sorunlu_dosyalari_sil(ad)):
            self.b.kayit(f"ONARIM {isim}: {n} sorunlu blok aynı araçla yeniden okunacak")
            return
        self._birak(a, ad, isim, f"teslim edilemedi ({sonuc.value}; ayrıntı: kontrol.txt)")


def kur(yollar: Yollar, kotalar: dict[str, int] | None = None) -> Zamanlayici:
    kotalar = kotalar or {}
    araclar = []
    for arac in ARACLAR:
        x = AracDurumu(arac, gunluk=kotalar.get(arac.model, GUNLUK_ISTEK))
        x.kapasite = kapasite(arac, yollar)
        araclar.append(x)
    return Zamanlayici(DurumDeposu(yollar.durum), gercek_bagimliliklar(yollar), araclar)
