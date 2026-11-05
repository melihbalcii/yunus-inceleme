"""Bölüm bölüm çevrilmiş eseri (podcast/<eser>/tr/NN.md) iki metne birleştirir:
  ceviri.txt               özgün yazım (okumak ve arşiv için)
  seslendirme-metni.txt    okuma metni: başlıklar okunur biçimde, yabancı adlar okunuşlarıyla, giriş ve kapanış duyurusu

Eserin ayarları podcast/<eser>/ceviri.json'dadır; yeni kitap için kod yazılmaz, yalnız bu dosya yazılır:
  {
    "bolum_sayisi": 46,
    "ceviri_basligi": "# Martin Eden\\nJack London",        (isteğe bağlı; ceviri.txt'nin başına)
    "giris": "Martin İdın. Cek Landın. İngilizce aslından çevrilmiştir.",
    "kapanis": ["Son.", "Cek Landın'un Martin İdın adlı romanını dinlediniz. ..."],
    "okunus": [["Martin Eden", "Martin İdın"], ...]            (uzun ad önce: sırayla uygulanır)
  }
Başlık biçimleri: "## Birinci Kısım" → "Birinci kısım."; "### IV" → "Dördüncü bölüm."; "### IV\\nBaşlık" →
"Dördüncü bölüm: Başlık." Başka "#" ile başlayan paragraf hata sayılır (gözden kaçmış biçim okunmasın).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .yollar import Yollar

HARF = "A-Za-zÇĞİÖŞÜçğıöşüÂâÎîÛû"
_BIRLER = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
_ONLAR = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]
_SIRA_EKI = {"bir": "birinci", "iki": "ikinci", "üç": "üçüncü", "dört": "dördüncü", "beş": "beşinci",
             "altı": "altıncı", "yedi": "yedinci", "sekiz": "sekizinci", "dokuz": "dokuzuncu", "on": "onuncu",
             "yirmi": "yirminci", "otuz": "otuzuncu", "kırk": "kırkıncı", "elli": "ellinci", "altmış": "altmışıncı",
             "yetmiş": "yetmişinci", "seksen": "sekseninci", "doksan": "doksanıncı"}
_ROMA = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
KISIM = re.compile(r"^## (\S+) Kısım$")
BOLUM = re.compile(r"^### ([IVXLC]+)(?:\n(.+))?$")


class CeviriHatasi(ValueError):
    pass


def roma(s: str) -> int:
    t = 0
    for i, h in enumerate(s):
        t += -_ROMA[h] if i + 1 < len(s) and _ROMA[h] < _ROMA[s[i + 1]] else _ROMA[h]
    return t


def sirali(n: int) -> str:
    """1 → "Birinci", 46 → "Kırk altıncı" (1-99)."""
    if not 0 < n < 100:
        raise CeviriHatasi(f"sıra sözcüğü yalnız 1-99 için: {n}")
    k = [x for x in (_ONLAR[n // 10], _BIRLER[n % 10]) if x]
    k[-1] = _SIRA_EKI[k[-1]]
    s = " ".join(k)
    return buyuk_harfle(s)


def buyuk_harfle(s: str) -> str:
    """İlk harfi Türkçe kuralla büyütür (str.upper "i"yi "I" yapar: "Ikinci bölüm" yanlış okunur)."""
    if not s:
        return s
    ilk = {"i": "İ", "ı": "I"}.get(s[0], s[0].upper())
    return ilk + s[1:]


@dataclass(frozen=True)
class CeviriAyari:
    bolum_sayisi: int
    giris: str
    kapanis: tuple[str, ...]
    okunus: tuple[tuple[str, str], ...]
    ceviri_basligi: str = ""

    @classmethod
    def oku(cls, dosya: Path) -> "CeviriAyari":
        try:
            v = json.loads(dosya.read_text(encoding="utf-8"))
            return cls(bolum_sayisi=int(v["bolum_sayisi"]), giris=v["giris"], kapanis=tuple(v["kapanis"]),
                       okunus=tuple((a, b) for a, b in v.get("okunus", [])), ceviri_basligi=v.get("ceviri_basligi", ""))
        except (OSError, ValueError, KeyError, TypeError) as h:
            raise CeviriHatasi(f"{dosya} okunamadı: {h}") from h


def okunusla(yazi: str, okunus: tuple[tuple[str, str], ...]) -> str:
    """Adları okunuşlarıyla değiştirir; yalnız tam sözcük olarak (önü harf olmamalı, ardından küçük harf gelmemeli:
    "Joe" → "Co", "Joey" değişmez; Türkçe ek kesme işaretiyle ayrıldığı için "Joe'nun" → "Co'nun")."""
    for a, b in okunus:
        yazi = re.sub(rf"(?<![{HARF}])" + re.escape(a) + r"(?![a-zçğıöşü])", b, yazi)
    return yazi.replace("\xad", "")


def birlestir(klasor: Path, ayar: CeviriAyari) -> tuple[str, str]:
    """(ceviri.txt, seslendirme-metni.txt) içerikleri."""
    ceviri: list[str] = []
    ses: list[str] = [ayar.giris]
    son_bolum = 0
    for i in range(1, ayar.bolum_sayisi + 1):
        dosya = klasor / "tr" / f"{i:02d}.md"
        try:
            t = dosya.read_text(encoding="utf-8").strip()
        except OSError as h:
            raise CeviriHatasi(f"bölüm dosyası yok: {dosya}") from h
        for p in t.split("\n\n"):
            ceviri.append(p)
            if m := KISIM.match(p):
                ses.append(f"{m.group(1)} kısım.")
                son_bolum = 0  # bölüm numaraları her kısımda baştan başlar
            elif m := BOLUM.match(p):
                n = roma(m.group(1))
                if n != son_bolum + 1:
                    raise CeviriHatasi(f"{dosya.name}: bölüm sırası bozuk ({son_bolum} → {n})")
                son_bolum = n
                ses.append(f"{sirali(n)} bölüm: {m.group(2).strip()}." if m.group(2) else f"{sirali(n)} bölüm.")
            elif p.startswith("#"):
                raise CeviriHatasi(f"{dosya.name}: tanınmayan başlık: {p[:40]!r}")
            else:
                ses.append(p)
    ses += ayar.kapanis
    bas = ayar.ceviri_basligi + "\n\n" if ayar.ceviri_basligi else ""
    return bas + "\n\n".join(ceviri) + "\n", okunusla("\n\n".join(ses) + "\n", ayar.okunus)


def okunussuz_adlar(seslendirme: str) -> list[str]:
    """Okunuşu yazılmamış olabilecek, İngilizce görünen büyük harfli sözcükler (gözden geçirmek için)."""
    adaylar = sorted(set(re.findall(r"\b[A-Z][a-z]+(?:-[a-z]+)?\b", seslendirme)))
    return [k for k in adaylar if re.search(r"[wqx]|th|ee|oo|sh|ck|gh", k.lower())]


def yaz(ad: str, yollar: Yollar) -> tuple[int, int]:
    """Eserin iki metnini yazar; (paragraf, kelime) sayısını döndürür."""
    klasor = yollar.eser_klasoru(ad)
    ceviri, ses = birlestir(klasor, CeviriAyari.oku(klasor / "ceviri.json"))
    for dosya, yazi in ((klasor / "ceviri.txt", ceviri), (klasor / "seslendirme-metni.txt", ses)):
        gecici = dosya.with_name(dosya.name + ".yaziliyor")
        gecici.write_text(yazi, encoding="utf-8")
        gecici.replace(dosya)
    return ses.count("\n\n") + 1, len(ses.split())
