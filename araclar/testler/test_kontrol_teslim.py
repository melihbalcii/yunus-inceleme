from __future__ import annotations

import json
import os
import time
import unittest

from testler.yardim import GeciciKokTesti, ses
from sesli import ses as S
from sesli.hazirlik import kuyruk, metni_hazirla, okunacak_mi
from sesli.katalog import Katalog
from sesli.kontrol import KontrolSonucu, kontrol_et
from sesli.teslim import TeslimDurumu, gecerli_teslim, teslim_et


class KontrolTesti(GeciciKokTesti):
    def okunmus(self, metinler: list[str]) -> None:
        fola = self.y.fola_klasoru("kisa-oyku")
        fola.mkdir(parents=True)
        plan = []
        for no, m in enumerate(metinler, 1):
            S.wav_yaz(self.y.parcalar / f"b{no}.wav", ses(0.2 * no))
            plan.append(dict(no=no, tarz="blok", dosya=f"b{no}.wav", metin=m))
        (fola / "plan.json").write_text(json.dumps(plan, ensure_ascii=False))

    def test_iyi_okuma_gecer_ve_onbellek_kullanilir(self):
        self.okunmus(["Bir iki üç dört.", "Beş altı yedi sekiz."])
        dokumler = {"b1.wav": "Bir, iki, üç, dört.", "b2.wav": "Beş altı yedi sekiz."}
        cagri = []

        def dok(dosya, kosullu):
            cagri.append(dosya.name)
            return dokumler[dosya.name]

        s = kontrol_et(self.y.fola_klasoru("kisa-oyku"), self.y.parcalar, bildir=lambda x: None, dok=dok)
        self.assertTrue(s.gecti)
        self.assertEqual(s.eslesme, 100.0)
        kontrol_et(self.y.fola_klasoru("kisa-oyku"), self.y.parcalar, bildir=lambda x: None, dok=dok)
        self.assertEqual(cagri, ["b1.wav", "b2.wav"])  # ikinci kontrol önbellekten
        geri = KontrolSonucu.oku(self.y.fola_klasoru("kisa-oyku"))
        self.assertTrue(geri.gecti)
        self.assertIn("harf düzeyinde eşleşme %100.00", (self.y.fola_klasoru("kisa-oyku") / "kontrol.txt").read_text())

    def test_atlama_varsa_gecmez_ve_ikinci_dinleme_denenir(self):
        metin = "Bir gün yaşlı adam denize açıldı ve uzun süre balık tuttu sonra evine döndü."
        self.okunmus([metin])
        kipler = []

        def dok(dosya, kosullu):
            kipler.append(kosullu)
            return "Bir gün yaşlı adam evine döndü."

        s = kontrol_et(self.y.fola_klasoru("kisa-oyku"), self.y.parcalar, bildir=lambda x: None, dok=dok)
        self.assertFalse(s.gecti)
        self.assertEqual(kipler, [False, True])
        self.assertEqual(s.sorunlu_bloklar(), [1])
        self.assertTrue(s.atlamalar)


class KontrolAyrintiTesti(KontrolTesti):
    """Whisper dökümü önbelleği, ikinci dinleme koşulları ve toplam eşleşmenin hesabı."""

    test_iyi_okuma_gecer_ve_onbellek_kullanilir = None  # type: ignore[assignment]  # üst sınıfın testleri bir kez
    test_atlama_varsa_gecmez_ve_ikinci_dinleme_denenir = None  # type: ignore[assignment]

    def kontrol(self, dok, bildir=lambda x: None):
        return kontrol_et(self.y.fola_klasoru("kisa-oyku"), self.y.parcalar, bildir=bildir, dok=dok)

    def test_onbellek_anahtari_dosya_ve_boyut_sessizlik_atlanir_bildirim(self):
        self.okunmus(["Bir iki üç.", "Dört beş."])
        plan = json.loads((self.y.fola_klasoru("kisa-oyku") / "plan.json").read_text())
        plan.insert(1, {"no": 9, "tarz": "sessizlik"})
        (self.y.fola_klasoru("kisa-oyku") / "plan.json").write_text(json.dumps(plan))
        mesajlar: list[str] = []
        s = self.kontrol(lambda d, k: {"b1.wav": "Bir iki üç.", "b2.wav": "Dört beş."}[d.name], mesajlar.append)
        self.assertEqual(mesajlar, ["[1/3] 1.000", "[2/3] 1.000"])
        self.assertEqual([b.no for b in s.bloklar], [1, 2])
        onbellek = json.loads((self.y.parcalar / "yazidokum.json").read_text())
        boy = {n: (self.y.parcalar / f"b{n}.wav").stat().st_size for n in (1, 2)}
        self.assertEqual(onbellek, {f"b1.wav|{boy[1]}": "Bir iki üç.", f"b2.wav|{boy[2]}": "Dört beş."})
        S.wav_yaz(self.y.parcalar / "b1.wav", ses(1.3))  # blok yeniden okundu: boyu değişti, yeniden dinlenir
        cagri: list[str] = []
        self.kontrol(lambda d, k: (cagri.append(d.name), "Bir iki üç.")[1])
        self.assertEqual(cagri, ["b1.wav"])

    def test_toplam_eslesme_harf_agirlikli_blok_raporu_alanlari(self):
        self.okunmus(["Bir iki.", "Üç dört beş altı yedi sekiz dokuz on."])
        s = self.kontrol(lambda d, k: {"b1.wav": "Bir.", "b2.wav": "Üç dört beş altı yedi sekiz dokuz on."}[d.name])
        b1 = s.bloklar[0]
        self.assertEqual((b1.metin, b1.duyulan, b1.kapsama), ("Bir iki.", "Bir.", 0.5))
        self.assertEqual(b1.oran, round(2 * 3 / (6 + 3), 3))
        from sesli.karsilastir import harf_eslesmesi
        _, e1, h1 = harf_eslesmesi("Bir iki.", "Bir.")
        _, e2, h2 = harf_eslesmesi(*[b.metin for b in s.bloklar[1:]] * 2)
        self.assertEqual((e1, h1, e2, h2), (3, 6, 29, 29))
        self.assertAlmostEqual(s.eslesme, 100 * (e1 + e2) / (h1 + h2), msg="blok ortalaması değil, harf ağırlıklı")

    def test_ikinci_dinleme_yalniz_uzun_ve_eksik_duyulan_blokta(self):
        kisa = "Bir iki üç dört beş altı yedi sekiz."  # 8 kelime: ikinci dinleme yok
        uzun = "Bir iki üç dört beş altı yedi sekiz dokuz."
        for metin, duyulan, beklenen in ((kisa, "Bir iki.", [False]), (uzun, uzun, [False]),
                                         (uzun, "Bir iki üç dört beş altı yedi.", [False, True])):
            with self.subTest(metin=metin, duyulan=duyulan):
                self.setUp()
                self.okunmus([metin])
                kipler: list[bool] = []
                self.kontrol(lambda d, k: (kipler.append(k), duyulan)[1])
                self.assertEqual(kipler, beklenen)

    def test_ikinci_dinleme_iyiyse_kalici_kotuyse_ilki_kalir(self):
        metin = "Bir gün yaşlı adam denize açıldı ve uzun süre balık tuttu sonra evine döndü."
        for ikinci, iyi_mi in ((metin, True), ("Bir.", False)):
            with self.subTest(iyi_mi=iyi_mi):
                self.setUp()
                self.okunmus([metin])
                s = self.kontrol(lambda d, k: ikinci if k else "Bir gün yaşlı adam evine döndü.")
                self.assertEqual(s.bloklar[0].duyulan, ikinci if iyi_mi else "Bir gün yaşlı adam evine döndü.")
                cagri: list[bool] = []
                self.kontrol(lambda d, k: (cagri.append(k), "x")[1])
                self.assertEqual(cagri, [], "iki kip de önbellekte: yeniden dinlenmez")
                self.assertEqual(self.kontrol(lambda d, k: "x").bloklar[0].duyulan, s.bloklar[0].duyulan)


class TeslimTesti(GeciciKokTesti):
    def hazir_okuma(self, gecti=True, bozuk=False, motor="Gemini 3.8 Flash Lite TTS"):
        fola = self.y.fola_klasoru("kisa-oyku")
        fola.mkdir(parents=True)
        S.mp3_yaz(fola / "kisa-oyku.mp3", ses(0.5))
        KontrolSonucu(eslesme=99.5 if gecti else 90.0).yaz(fola)
        (fola / "kalite.json").write_text(json.dumps([{"no": 1, "bas": 3.5, "son": 3.5, "bozuk": bozuk}]))
        (fola / "motor.json").write_text(json.dumps({"motor": motor, "model": "m", "ses": "Fola"}))
        return Katalog.yukle(self.y).al("kisa-oyku")

    def test_konulur_ve_kunye_yazilir(self):
        eser = self.hazir_okuma()
        s = teslim_et(eser, self.y)
        self.assertIs(s.durum, TeslimDurumu.KONULDU)
        self.assertEqual(s.hedef, self.y.teslim / "Gemini 3.8 Flash Lite" / "01 - Kısa Öykü - Yazar Bir.mp3")
        from mutagen.id3 import ID3
        k = ID3(s.hedef)
        self.assertEqual(str(k["TIT2"]), "Kısa Öykü")
        self.assertIn("Gemini 3.8 Flash Lite TTS, Fola", str(k.getall("COMM")[0]))
        self.assertIs(teslim_et(eser, self.y).durum, TeslimDurumu.GUNCEL)

    def test_kontrolden_gecmeyen_konmaz(self):
        self.assertIs(teslim_et(self.hazir_okuma(gecti=False), self.y).durum, TeslimDurumu.KONTROLDEN_GECMEDI)

    def test_bozuk_ses_konmaz(self):
        self.assertIs(teslim_et(self.hazir_okuma(bozuk=True), self.y).durum, TeslimDurumu.KALITE_DUSUK)

    def test_live_klasorune_konmaz(self):
        self.assertIs(teslim_et(self.hazir_okuma(motor="Gemini 3.8 Live"), self.y).durum,
                      TeslimDurumu.ARAC_BILINMIYOR)

    def test_baska_aracin_eski_hali_cope_tasinir(self):
        eski = self.y.teslim / "Gemini 3.8 Flash" / "01 - Kısa Öykü - Yazar Bir.mp3"
        eski.parent.mkdir()
        eski.write_bytes(b"eski")
        os.utime(eski, (time.time() - 3600, time.time() - 3600))
        s = teslim_et(self.hazir_okuma(), self.y)
        self.assertIs(s.durum, TeslimDurumu.KONULDU)
        self.assertFalse(eski.exists())
        self.assertEqual([c.name for c in s.cope], ["Gemini 3.8 Flash - 01 - Kısa Öykü - Yazar Bir.mp3"])
        self.assertEqual(gecerli_teslim(Katalog.yukle(self.y).al("kisa-oyku"), self.y), s.hedef)


class HazirlikTesti(GeciciKokTesti):
    def test_kuyruk_kisadan_uzuna_ve_kosullar(self):
        self.metin_yaz("kisa-oyku", ["kısa"])
        self.metin_yaz("uzun-roman", ["uzun " * 50])
        self.metin_yaz("emel-eseri", ["emel"])     # Emel kopyası yok: okunmaz
        self.metin_yaz("birakilan", ["vazgeçildi"])
        k = Katalog.yukle(self.y)
        self.assertEqual([i.ad for i in kuyruk(k, self.y)], ["kisa-oyku", "uzun-roman"])
        (self.y.emel_teslim / k.al("emel-eseri").dosya_adi).write_bytes(b"x")
        self.assertEqual([i.ad for i in kuyruk(k, self.y)], ["emel-eseri", "kisa-oyku", "uzun-roman"])

    def test_metni_olmayan_eser_kuyrugu_durdurmaz(self):
        self.metin_yaz("kisa-oyku", ["kısa"])  # uzun-roman'ın metni yok
        uyarilar: list[str] = []
        isler = kuyruk(Katalog.yukle(self.y), self.y, hazirla=True, uyar=uyarilar.append)
        self.assertEqual([i.ad for i in isler], ["kisa-oyku"])
        self.assertEqual(len(uyarilar), 1)
        self.assertIn("uzun-roman", uyarilar[0])

    def test_teslim_edilen_kuyruktan_cikar_yeniden_okununca_girer(self):
        self.metin_yaz("kisa-oyku", ["kısa"])
        eser = Katalog.yukle(self.y).al("kisa-oyku")
        t = self.y.teslim / "Gemini 3.8 Flash" / eser.dosya_adi
        t.parent.mkdir()
        t.write_bytes(b"x")
        self.assertFalse(okunacak_mi(eser, self.y))
        okuma = self.y.fola_klasoru("kisa-oyku") / "kisa-oyku.mp3"
        okuma.parent.mkdir(parents=True)
        okuma.write_bytes(b"y")
        os.utime(t, (time.time() - 60, time.time() - 60))
        self.assertTrue(okunacak_mi(eser, self.y))

    def test_metni_hazirla_degismediyse_dokunmaz(self):
        self.metin_yaz("kisa-oyku", ["Bir.", "  İki.  "])
        eser = Katalog.yukle(self.y).al("kisa-oyku")
        d = metni_hazirla(eser, self.y)
        self.assertEqual(d.read_text(encoding="utf-8"), "Bir.\n\nİki.\n")
        once = d.stat().st_mtime_ns
        time.sleep(0.01)
        metni_hazirla(eser, self.y)
        self.assertEqual(d.stat().st_mtime_ns, once)

    def test_parcali_eser_birlestirilir(self):
        k = self.y.eser_klasoru("kisa-oyku")
        for n, ps in enumerate([["Eser. Yazar. Birinci kısım.", "A.", "Birinci kısmın sonu."],
                                ["Eser. İkinci kısım.", "B.", "Eser'i dinlediniz."]], 1):
            (k / f"kisim-{n}").mkdir(parents=True)
            (k / f"kisim-{n}" / "seslendirme-metni.txt").write_text("\n\n".join(ps), encoding="utf-8")
        d = metni_hazirla(Katalog.yukle(self.y).al("kisa-oyku"), self.y)
        self.assertEqual(d.read_text(encoding="utf-8"), "Eser. Yazar.\n\nA.\n\nB.\n\nEser'i dinlediniz.\n")


class BirlesikParagrafTesti(GeciciKokTesti):
    """Parçalı eserler (kısım, bölüm, boy) tek okuma metnine: hiçbir bölüm atlanmamalı ya da iki kez okunmamalı."""

    def parcalar(self, tur, *parcalar):
        from sesli.hazirlik import birlesik_paragraflar
        k = self.kok / "eser"
        for n, ps in enumerate(parcalar, 1):
            (k / f"{tur}-{n:02d}" if tur == "boy" else k / f"{tur}-{n}").mkdir(parents=True)
            d = (k / f"{tur}-{n:02d}") if tur == "boy" else (k / f"{tur}-{n}")
            (d / "seslendirme-metni.txt").write_text("\n\n".join(ps), encoding="utf-8")
        return birlesik_paragraflar(k)

    def test_boylar_giris_ve_kapanislar_tek_kez_kalir(self):
        sonuc = self.parcalar("boy",
                              ["Dede Korkut Hikâyeleri. Birinci boy: Dirse Han.", "A.", "Birinci boyunu dinlediniz."],
                              ["Dede Korkut Hikâyeleri. İkinci boy: Bamsı.", "B.", "Dede Korkut'un ikinci boyunu dinlediniz."])
        self.assertEqual(sonuc, ["Dede Korkut Hikâyeleri. Birinci boy: Dirse Han.", "A.", "İkinci boy: Bamsı.", "B.",
                                 "Dede Korkut'u dinlediniz."])

    def test_kapanissiz_boy_hata(self):
        from sesli.hazirlik import MetinHatasi
        with self.assertRaises(MetinHatasi):
            self.parcalar("boy", ["Eser. Birinci boy.", "A."], ["Eser. İkinci boy.", "B.", "dinlediniz."])

    def test_bolumlerde_sira_basligi_bir_kez_kalir(self):
        sonuc = self.parcalar("bolum", ["Eser. Yazar. Birinci bölüm.", "Birinci bölüm.", "A.", "Birinci bölümün sonu."],
                              ["Eser. İkinci bölüm.", "İkinci bölüm.", "B.", "Eserin ikinci bölümünü dinlediniz."])
        self.assertEqual(sonuc, ["Eser. Yazar.", "A.", "B.", "Eseri dinlediniz."])

    def test_gecis_duyurusu_olmayan_parca_hata(self):
        from sesli.hazirlik import MetinHatasi
        with self.assertRaises(MetinHatasi):
            self.parcalar("kisim", ["Eser. Birinci kısım.", "A.", "Burada duyuru yok."], ["Eser. İkinci kısım.", "B."])


class KuyrukHazirlikTesti(GeciciKokTesti):
    """Kuyruk ve okuma metni: önizleme diske yazmaz; zamanlayıcı metni günceller; eşit uzunlukta ad sırası."""

    def test_onizleme_yazmaz_uzunlugu_kaynaktan_olcer(self):
        self.metin_yaz("kisa-oyku", ["abc"])
        self.metin_yaz("uzun-roman", ["abcdef"])
        isler = kuyruk(Katalog.yukle(self.y), self.y)
        self.assertEqual([(i.ad, i.uzunluk) for i in isler], [("kisa-oyku", 4), ("uzun-roman", 7)])
        self.assertFalse(self.y.fola_klasoru("kisa-oyku").exists(), "önizleme dosya yazmamalı")

    def test_hazir_okuma_metni_varsa_uzunluk_ondan(self):
        self.metin_yaz("kisa-oyku", ["abc"])
        f = self.y.fola_klasoru("kisa-oyku")
        f.mkdir(parents=True)
        (f / "seslendirme-metni.txt").write_text("x" * 50, encoding="utf-8")
        (i,) = [i for i in kuyruk(Katalog.yukle(self.y), self.y) if i.ad == "kisa-oyku"]
        self.assertEqual((i.uzunluk, i.metin_dosyasi), (50, f / "seslendirme-metni.txt"))

    def test_zamanlayici_metni_kaynaga_gore_gunceller_yarim_dosya_birakmaz(self):
        self.metin_yaz("kisa-oyku", ["abc"])
        f = self.y.fola_klasoru("kisa-oyku")
        f.mkdir(parents=True)
        (f / "seslendirme-metni.txt").write_text("eski", encoding="utf-8")
        (i,) = [i for i in kuyruk(Katalog.yukle(self.y), self.y, hazirla=True) if i.ad == "kisa-oyku"]
        self.assertEqual((f / "seslendirme-metni.txt").read_text(encoding="utf-8"), "abc\n")
        self.assertEqual(i.uzunluk, 4)
        self.assertEqual([p.name for p in f.iterdir()], ["seslendirme-metni.txt"])

    def test_esit_uzunlukta_ad_sirasi(self):
        self.metin_yaz("uzun-roman", ["abc"])
        self.metin_yaz("kisa-oyku", ["xyz"])
        self.assertEqual([i.ad for i in kuyruk(Katalog.yukle(self.y), self.y)], ["kisa-oyku", "uzun-roman"])


class KunyeTesti(GeciciKokTesti):
    def test_kunye_alanlari_eksiksiz_ve_utf8(self):
        from mutagen.id3 import ID3
        from sesli.teslim import kunye_yaz
        mp3 = self.kok / "a.mp3"
        S.mp3_yaz(mp3, ses(0.3))
        kunye_yaz(mp3, Katalog.yukle(self.y).al("kisa-oyku"), "Gemini 3.8 Flash TTS", "Fola")
        k = ID3(mp3)
        alanlar = ("TIT2", "TPE1", "TALB", "TCON", "TLAN", "TDRC")  # ID3 v2.4: yıl (TYER) TDRC olarak kaydedilir
        self.assertEqual({a: str(k[a]) for a in alanlar},
                         {"TIT2": "Kısa Öykü", "TPE1": "Yazar Bir", "TALB": "Sesli Klasikler", "TCON": "Sesli Kitap",
                          "TLAN": "tur", "TDRC": "2026"})
        self.assertTrue(all(k[a].encoding == 3 for a in alanlar[:5]), "Türkçe harfli alanlar UTF-8 (yıl yalnız rakam)")
        (yorum,) = k.getall("COMM")
        self.assertEqual((yorum.lang, yorum.desc, yorum.encoding), ("tur", "", 3))
        self.assertEqual(str(yorum), "Bu kayıt yapay zekâ sesiyle (Gemini 3.8 Flash TTS, Fola) seslendirilmiştir.")


class CopeTasimaTesti(GeciciKokTesti):
    """Hiçbir şey silinmez: eski teslim kopyası Çöp Sepeti'ne gider, oradaki aynı adlı dosyanın üzerine yazılmaz."""

    def test_ayni_adli_dosya_ezilmez_sayi_eklenir(self):
        from sesli.teslim import cope_tasi
        adlar = []
        for icerik in (b"bir", b"iki", b"uc"):
            d = self.kok / "eski.mp3"
            d.write_bytes(icerik)
            hedef = cope_tasi(d, "Kayıt.mp3", self.y)
            adlar.append(hedef.name)
            self.assertFalse(d.exists())
            self.assertEqual(hedef.parent, self.y.cop)
            self.assertEqual(hedef.read_bytes(), icerik)
        self.assertEqual(adlar, ["Kayıt.mp3", "Kayıt (2).mp3", "Kayıt (3).mp3"])
        self.assertEqual(sorted(p.read_bytes() for p in self.y.cop.iterdir()), [b"bir", b"iki", b"uc"])


class KontrolSonucuTesti(GeciciKokTesti):
    """Teslimin son kapısı: eşikler sınır değerlerde doğru, kayıt okunup yazılınca aynı kalır."""

    def blok(self, no, oran, atlama=(), kapsama=1.0, metin="metin", duyulan="duyulan"):
        from sesli.kontrol import BlokRaporu
        return BlokRaporu(no=no, oran=oran, kapsama=kapsama, metin=metin, duyulan=duyulan, atlama=list(atlama))

    def test_gecme_esikleri_sinirda(self):
        self.assertTrue(KontrolSonucu(97.0, [self.blok(1, 0.90)]).gecti, "97,00 ve 0,90 tam eşik: geçer")
        self.assertFalse(KontrolSonucu(96.99, [self.blok(1, 0.99)]).gecti)
        self.assertFalse(KontrolSonucu(99.0, [self.blok(1, 0.899)]).gecti)
        self.assertFalse(KontrolSonucu(99.0, [self.blok(1, 0.99, ["atlanan"])]).gecti)
        self.assertTrue(KontrolSonucu(99.0, []).gecti)

    def test_sorunlu_bloklar_ve_sayimlar(self):
        k = KontrolSonucu(98.0, [self.blok(1, 0.99), self.blok(2, 0.85), self.blok(3, 0.97, ["a", "b"]),
                                 self.blok(4, 0.92)])
        self.assertEqual(k.sorunlu_bloklar(), [2, 3])
        self.assertEqual(k.dusuk, 1)
        self.assertEqual(k.atlamalar, [(3, "a"), (3, "b")])

    def test_yazilip_okununca_ayni_kalir_ozet_dosyasi_yazilir(self):
        k = KontrolSonucu(98.456, [self.blok(1, 0.93, ["atlanan söz"], kapsama=0.8, metin="m" * 300, duyulan="d"),
                                   self.blok(2, 0.99)])
        k.yaz(self.kok)
        veri = json.loads((self.kok / "kontrol.json").read_text())
        self.assertEqual((veri["eslesme"], veri["gecti"]), (98.46, False))
        geri = KontrolSonucu.oku(self.kok)
        assert geri is not None
        self.assertEqual((geri.eslesme, geri.bloklar), (98.46, k.bloklar))
        ozet = (self.kok / "kontrol.txt").read_text()
        for parca in ("[1/2] 0.930", "PARAGRAF 2 | harf düzeyinde eşleşme %98.46", "0,95 altı: 1 | 0,90 altı: 0",
                      "ATLAMA #1: «atlanan söz»", "KAPSAMA DÜŞÜK #1 %80", "- #1 0.930\n  metin  : " + "m" * 200 + "\n"):
            self.assertIn(parca, ozet)
        self.assertNotIn("KAPSAMA DÜŞÜK #2", ozet)
        self.assertNotIn("m" * 201, ozet, "uzun metin 200 harfte kesilir")

    def test_bozuk_ya_da_eksik_kayit_none(self):
        self.assertIsNone(KontrolSonucu.oku(self.kok))
        for icerik in ("{bozuk", '{"bloklar": []}', '{"eslesme": 99, "bloklar": [{"no": 1}]}', '{"eslesme": "yok"}'):
            (self.kok / "kontrol.json").write_text(icerik)
            self.assertIsNone(KontrolSonucu.oku(self.kok), icerik)


if __name__ == "__main__":
    unittest.main()
