"""Metin ile Whisper dökümünü karşılaştırma (saf işlevler).

Whisper sayıları rakamla, sıra sözcüklerini "4. Bölüm" diye yazar ve sessiz kuyrukta altyazı kalıpları uydurur;
karşılaştırmadan önce iki taraf da aynı biçime getirilir. Eşleşme harf düzeyindedir (Whisper ekleri ayırabiliyor:
"ruble lik"). Atlama: metnin seste karşılığı olmayan, en az üç kelime ve on harflik parçası.
"""
from __future__ import annotations

import difflib
import re

_BIR = ["sıfır", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
ON, YUZ = 10, 100
_ON = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]


def sayi(n: int | str) -> str:
    """Sayının okunuşu: 1915 → "bin dokuz yüz on beş"."""
    n = int(n)
    if n < ON:
        return _BIR[n]
    if n < YUZ:
        return (_ON[n // 10] + ("" if n % 10 == 0 else " " + _BIR[n % 10])).strip()
    for b, ad in ((10**6, "milyon"), (1000, "bin"), (100, "yüz")):
        if n >= b:
            bas = "" if n // b == 1 and b < 10**6 else sayi(n // b) + " "
            return (bas + ad + ("" if n % b == 0 else " " + sayi(n % b))).strip()
    return str(n)


def kelimeler(s: str) -> list[str]:
    s = re.sub(r"\d+", lambda m: " " + sayi(m.group()) + " ", s)
    s = s.replace("I", "ı").replace("İ", "i").lower().replace("â", "a")
    return re.findall(r"[a-zçğıöşüîû]+", s)


def sade_kelimeler(s: str) -> list[str]:
    return [k.replace("î", "i").replace("û", "u") for k in kelimeler(s)]


# Whisper'ın yazıya dökemediği uydurma sözler (Cthulhu'daki büyü): seste okunsa da "duyulmadı" görünür
OKUNAMAZ = set(sade_kelimeler("Fınglui mıglunaf Kutulu Rılyeh vğanagıl ftagın"))

# Whisper'ın sessiz kuyrukta uydurduğu altyazı kalıpları (seste yok)
UYDURMA = re.compile(r"(Altyazı M\.?K\.?|İzlediğiniz için teşekkür ederim\.?|Abone olmayı unutmayın\.?"
                     r"|Bu dizinin betimlemesi[^.]*\.)", re.I)

_SIRA = [x.replace("_", " ") for x in [
    "birinci", "ikinci", "üçüncü", "dördüncü", "beşinci", "altıncı", "yedinci", "sekizinci", "dokuzuncu", "onuncu",
    "on_birinci", "on_ikinci", "on_üçüncü", "on_dördüncü", "on_beşinci", "on_altıncı", "on_yedinci", "on_sekizinci",
    "on_dokuzuncu", "yirminci"]]
KAYIP_EN_AZ_KELIME, KAYIP_EN_AZ_HARF = 3, 10


def sira_sozcuk(s: str) -> str:
    """Whisper "4. Bölüm" yazar, metinde "Dördüncü bölüm" vardır."""
    return re.sub(r"\b(\d{1,2})\.\s*(?=[Bb]ölüm|[Kk]ısım|[Bb]oy|[Mm]asal|[Öö]ykü)",
                  lambda m: _SIRA[int(m.group(1)) - 1] + " " if 0 < int(m.group(1)) <= len(_SIRA) else m.group(0), s)


def duyulani_arit(duyulan: str) -> str:
    return sira_sozcuk(UYDURMA.sub(" ", duyulan))


def kayip_mi(metin_parcasi: list[str], duyulan_parca: list[str]) -> bool:
    """Metnin bu parçası seste gerçekten yok mu? Yazım farkı sayılmaz ("Hacegân'dan" metinde iki, Whisper'da tek
    kelime): harfler tutuyorsa atlama değildir. En az 3 kelime ve 10 harf eksik olmalı."""
    a, b = "".join(metin_parcasi), "".join(duyulan_parca)
    es = sum(x.size for x in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()) if b else 0
    if sum(k in OKUNAMAZ for k in metin_parcasi) * 3 >= len(metin_parcasi) * 2:
        return False
    return len(metin_parcasi) - len(duyulan_parca) >= KAYIP_EN_AZ_KELIME and len(a) - es >= KAYIP_EN_AZ_HARF


def atlamalar(hedef: list[str], duy: list[str]) -> list[str]:
    """Seste karşılığı olmayan metin parçaları (sade kelime listeleri üzerinden)."""
    return [" ".join(hedef[i1:i2])
            for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, hedef, duy, autojunk=False).get_opcodes()
            if op in ("delete", "replace") and kayip_mi(hedef[i1:i2], duy[j1:j2])]


def harf_eslesmesi(metin: str, duyulan: str) -> tuple[float, int, int]:
    """(oran, eşleşen harf, metnin harf sayısı); duyulan Whisper dökümüdür (henüz arıtılmamış)."""
    hedef = "".join(kelimeler(metin))
    duy = "".join(kelimeler(duyulani_arit(duyulan)))
    sm = difflib.SequenceMatcher(None, hedef, duy, autojunk=False)
    return sm.ratio(), sum(b.size for b in sm.get_matching_blocks()), len(hedef)


def olcum(metin: str, duyulan: str) -> tuple[float, list[str]]:
    """Bir bloğun (oran, atlamalar) ölçüsü."""
    oran, _, _ = harf_eslesmesi(metin, duyulan)
    return oran, atlamalar(sade_kelimeler(metin), sade_kelimeler(duyulani_arit(duyulan)))
