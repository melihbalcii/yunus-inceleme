"""Yeni kodun eski betiklerle aynı sonucu verdiğini GERÇEK veriyle denetler.

En önemli şart: okunmuş blokların önbellek adları (metin + model + ses + üslup özeti) değişmemeli; yoksa yarım
kalan eserler baştan okunur ve günlük kota boşa harcanır. Eski betikler .tmp/yeniden-yapi-oncesi/araclar'da
yedektir; yedek ya da gerçek veri yoksa testler atlanır. Yavaştır (eski betikler torch'u yükler):
  .venv-ses/bin/python -m unittest testler.uyumluluk   (araclar/ içinden)
"""
from __future__ import annotations

import importlib
import json
import random
import sys
import unittest

from testler.yardim import ARACLAR
from sesli import karsilastir as K
from sesli import metin as M
from sesli.hazirlik import kuyruk, okuma_metni
from sesli.katalog import Katalog
from sesli.okuma import OkumaAyari, blok_dosyasi
from sesli.yollar import Yollar

Y = Yollar.varsayilan()
ESKI = Y.tmp / "yeniden-yapi-oncesi" / "araclar"


def eski(modul: str):
    if not ESKI.exists():
        raise unittest.SkipTest("eski betiklerin yedeği yok")
    sys.path.insert(0, str(ESKI))
    try:
        m = importlib.import_module(modul)
    finally:
        sys.path.remove(str(ESKI))
        if str(ARACLAR) not in sys.path:
            sys.path.insert(0, str(ARACLAR))
    # yedekteki betikler proje kökünü kendi yerlerinden hesaplar: gerçek köke yönlendir
    for ad in (modul, "birlestir", "fola_kuyruk", "seslendir_gemini", "emel_kontrol"):
        if ad in sys.modules and hasattr(sys.modules[ad], "KOK"):
            sys.modules[ad].KOK = Y.kok
    return m


def okuma_metinleri() -> dict[str, str]:
    sonuc = {}
    for d in sorted(Y.podcast.glob("*/fola/seslendirme-metni.txt")):
        sonuc[d.parent.parent.name] = d.read_text(encoding="utf-8")
    if not sonuc:
        raise unittest.SkipTest("okuma metni yok")
    return sonuc


class MetinUyumuTesti(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = eski("seslendir_gemini")
        cls.metinler = okuma_metinleri()

    def test_sabit_bloklar_ayni(self):
        for ad, yazi in self.metinler.items():
            for sinir in (None, 2000, 3400):
                with self.subTest(eser=ad, sinir=sinir):
                    yol = Y.fola_klasoru(ad) / "seslendirme-metni.txt"
                    eskisi = [m for _, m in self.g.bloklar(yol, False, az_istek=True, en_cok=sinir)]
                    self.assertEqual(M.sabit_bloklar(yazi, False, sinir), eskisi)

    def test_paragraflar_ayni(self):
        for ad, yazi in self.metinler.items():
            with self.subTest(eser=ad):
                eskisi = self.g.paragraflar(Y.fola_klasoru(ad) / "seslendirme-metni.txt")
                self.assertEqual([(p.metin, p.devam) for p in M.paragraflar(yazi)], eskisi)

    def test_sonraki_sinir_ayni(self):
        r = random.Random(7)
        for ad, yazi in self.metinler.items():
            yeni = M.paragraflar(yazi)
            eskisi = [(p.metin, p.devam) for p in yeni]
            for _ in range(20):
                i, hiz, hedef = r.randrange(len(yeni)), r.uniform(8, 20), r.choice([470, 570, 1134, 1200])
                with self.subTest(eser=ad, i=i):
                    self.assertEqual(M.sonraki_sinir(yeni, i, hiz, hedef), self.g.sonraki_blok(eskisi, i, hiz, hedef))

    def test_cumleler_ayni(self):
        for ad, yazi in self.metinler.items():
            with self.subTest(eser=ad):
                self.assertEqual(M.cumleler(yazi[:20000]), self.g.cumleler(yazi[:20000]))


class OnbellekUyumuTesti(unittest.TestCase):
    """Her eserin kayıtlı blok planı yeni kodla yeniden kurulunca blok dosyaları önbellekte bulunmalı."""

    def test_okunmus_bloklar_taninir(self):
        planlar = sorted(Y.podcast.glob("*/fola/blok-plan.json"))
        if not planlar:
            self.skipTest("blok planı yok")
        bulunan = 0
        for plan_dosyasi in planlar:
            ad = plan_dosyasi.parent.parent.name
            kayit = json.loads(plan_dosyasi.read_text())
            kimlik, sinirlar = kayit["kimlik"], kayit["sinirlar"]
            par = M.paragraflar((plan_dosyasi.parent / "seslendirme-metni.txt").read_text(encoding="utf-8"))
            if (len(par), sum(len(p.metin) for p in par)) != (kimlik["paragraf"], kimlik["karakter"]):
                continue  # metni sonradan değişmiş eser: eski plan zaten geçersiz
            # aynı sesle ortak okuyan araçların blokları da geçerli (Beyaz Diş: Lite başladı, Flash sürdürdü)
            ortak = tuple(m for m in ("gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts") if m != kimlik["model"])
            ayar = OkumaAyari(model=kimlik["model"], ses=kimlik["ses"], ortak=ortak, hedef_sn=600)
            i = 0
            for j in sinirlar:
                d = blok_dosyasi(Y.parcalar, M.birlestir(par[i:j]), ayar)
                with self.subTest(eser=ad, blok=j):
                    self.assertTrue(d.exists(), f"{ad}: {d.name} önbellekte yok")
                bulunan += 1
                i = j
        self.assertGreater(bulunan, 0)


class GercekVeriTesti(unittest.TestCase):
    def test_eser_listesi_gecerli_ve_klasorler_var(self):
        k = Katalog.yukle(Y)
        for e in k.etkinler():
            with self.subTest(eser=e.ad):
                self.assertTrue(Y.eser_klasoru(e.ad).is_dir())

    def test_teslim_klasorundeki_her_dosya_listede(self):
        k = Katalog.yukle(Y)
        for mp3 in Y.teslim.glob("*/*.mp3"):
            with self.subTest(dosya=mp3.name):
                eser = k.numarayla(int(mp3.name.split(" - ")[0]))
                self.assertIsNotNone(eser)
                self.assertEqual(mp3.name, eser.dosya_adi)

    def test_ceviri_ayarlari_metinleri_aynen_uretir(self):
        from sesli import ceviri
        for ayar in sorted(Y.podcast.glob("*/ceviri.json")):
            k = ayar.parent
            with self.subTest(eser=k.name):
                c, s = ceviri.birlestir(k, ceviri.CeviriAyari.oku(ayar))
                self.assertEqual(c, (k / "ceviri.txt").read_text(encoding="utf-8"))
                self.assertEqual(s, (k / "seslendirme-metni.txt").read_text(encoding="utf-8"))


class KuyrukUyumuTesti(unittest.TestCase):
    def test_kuyruk_eski_siraya_esit(self):
        fk = eski("fola_kuyruk")
        eskisi = [(n, ad) for n, ad, _, _ in fk.sira()]
        yenisi = [(i.uzunluk, i.ad) for i in kuyruk(Katalog.yukle(Y), Y)]
        self.assertEqual(yenisi, eskisi)

    def test_okuma_metni_eskisiyle_ayni(self):
        b = eski("birlestir")
        for e in Katalog.yukle(Y).etkinler():
            k = Y.eser_klasoru(e.ad)
            if not (k / "seslendirme-metni.txt").exists() and not b.birimler(k):
                continue
            with self.subTest(eser=e.ad):
                eskisi = b.metin(e.ad) if b.birimler(k) else [
                    p.strip() for p in (k / "seslendirme-metni.txt").read_text(encoding="utf-8").split("\n\n")
                    if p.strip()]
                self.assertEqual(okuma_metni(e, Y), "\n\n".join(eskisi) + "\n")


class KarsilastirmaUyumuTesti(unittest.TestCase):
    def test_whisper_dokumleriyle_ayni_olcu(self):
        ek = eski("emel_kontrol")
        d = Y.parcalar / "yazidokum.json"
        plan = Y.parcalar / "son-plan.json"
        if not d.exists() or not plan.exists():
            self.skipTest("döküm önbelleği yok")
        dokum = json.loads(d.read_text())
        for p in json.loads(plan.read_text()):
            duyulan = next((v for k, v in dokum.items() if k.startswith(f"{p['dosya']}|") and "|2" not in k[-2:]), None)
            if duyulan is None:
                continue
            with self.subTest(blok=p["no"]):
                h, dy = ek.kelimeler(p["metin"]), ek.kelimeler(ek.sira_sozcuk(ek.UYDURMA.sub(" ", duyulan)))
                import difflib
                eski_oran = difflib.SequenceMatcher(None, "".join(h), "".join(dy), autojunk=False).ratio()
                self.assertAlmostEqual(K.harf_eslesmesi(p["metin"], duyulan)[0], eski_oran, places=12)
                h2, d2 = ek.sade_kelimeler(p["metin"]), ek.sade_kelimeler(ek.sira_sozcuk(ek.UYDURMA.sub(" ", duyulan)))
                eski_atlama = [" ".join(h2[i1:i2]) for op, i1, i2, j1, j2 in
                               difflib.SequenceMatcher(None, h2, d2, autojunk=False).get_opcodes()
                               if op in ("delete", "replace") and ek.kayip_mi(h2[i1:i2], d2[j1:j2])]
                self.assertEqual(K.olcum(p["metin"], duyulan)[1], eski_atlama)


if __name__ == "__main__":
    unittest.main()
