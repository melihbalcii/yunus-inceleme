"""Zamanlayıcı: bütün dış bağımlılıklar sahte (alt süreç, teslim, saat)."""
from __future__ import annotations

import datetime as dt
import json
import unittest
from pathlib import Path

from testler.yardim import GeciciKokTesti
from sesli import zamanlayici as Z
from sesli.durum import DurumDeposu
from sesli.gemini import Arac
from sesli.hazirlik import KuyrukIsi
from sesli.isci import Cikis
from sesli.katalog import Katalog
from sesli.teslim import TeslimDurumu

LITE = Arac("Lite TTS", "lite", "Fola")
FLASH = Arac("Flash TTS", "flash", "Fola")
K31 = Arac("3.1 TTS", "k31", "Sulafat", sabit_blok=2000)


class Sahne:
    def __init__(self, test: GeciciKokTesti, boylar: dict[str, int]):
        self.boylar = dict(boylar)
        self.cikislar: list[Cikis] = []
        self.teslimler: list[TeslimDurumu] = []
        self.isler: list = []
        self.kayitlar: list[str] = []
        self.beklemeler: list[dt.datetime] = []
        self.silinen = 0
        self.simdi = dt.datetime(2026, 11, 5, 12, 0)
        katalog = Katalog.yukle(test.y)

        def kuyruk(_k):
            return sorted((KuyrukIsi(katalog.al(a), n, Path("/yok")) for a, n in self.boylar.items()),
                          key=lambda i: (i.uzunluk, i.ad))

        def calistir(is_):
            self.isler.append(is_)
            return self.cikislar.pop(0)

        def teslim(ad):
            d = self.teslimler.pop(0)
            if d is TeslimDurumu.KONULDU:
                self.boylar.pop(ad)
            return d

        def bekle(bitis):
            self.beklemeler.append(bitis)
            self.simdi = bitis

        def sil(_ad):
            self.silinen += 1
            return 2

        self.b = Z.Bagimliliklar(katalog=lambda: katalog, kuyruk=kuyruk, calistir=calistir, teslim=teslim,
                                 sorunlu_dosyalari_sil=sil, bekle=bekle, simdi=lambda: self.simdi,
                                 kayit=self.kayitlar.append, hedef_sn=lambda m: 1000)
        self.depo = DurumDeposu(test.y.durum)

    def zamanlayici(self, gunluk=(10, 10, 10)) -> Z.Zamanlayici:
        araclar = [Z.AracDurumu(a, g, kapasite=100_000) for a, g in zip((LITE, FLASH, K31), gunluk)]
        return Z.Zamanlayici(self.depo, self.b, araclar)


class ZamanlayiciTesti(GeciciKokTesti):
    def test_eser_okunur_teslim_edilir_ve_biter(self):
        s = Sahne(self, {"kisa-oyku": 1000})
        s.cikislar = [Cikis.TAMAM]
        s.teslimler = [TeslimDurumu.KONULDU]
        s.zamanlayici().calis(tur_siniri=5)
        self.assertEqual(s.isler[0].model, "lite")
        self.assertEqual(s.isler[0].hedef_sn, 1000)
        self.assertEqual(s.kayitlar[-1], "HEPSİ BİTTİ")
        self.assertEqual(s.depo.oku().atama, {})
        self.assertEqual(s.depo.oku().yontem, {"kisa-oyku": "uyarlamali"})

    def test_kota_dolunca_sonraki_arac_ve_ertesi_gun_ayni_arac(self):
        s = Sahne(self, {"kisa-oyku": 1000})
        s.cikislar = [Cikis.KOTA, Cikis.TAMAM]
        s.teslimler = [TeslimDurumu.KONULDU]
        z = s.zamanlayici(gunluk=(10, 10, 0))
        z.calis(tur_siniri=6)
        # Lite'a atanmış eser Flash'a geçmez (tek ses); Flash'ın başka işi yok → bekleme, ertesi gün Lite sürer
        self.assertEqual([i.model for i in s.isler], ["lite", "lite"])
        self.assertEqual(len(s.beklemeler), 1)
        self.assertEqual(s.beklemeler[0], dt.datetime(2026, 11, 6, 11, 5))  # kışın Pasifik gece yarısı = TR 11:00

    def test_ortak_arac_eseri_surdurur(self):
        s = Sahne(self, {"kisa-oyku": 1000})
        with s.depo.degistir() as d:
            d.atama["kisa-oyku"] = "lite"
            d.yontem["kisa-oyku"] = "uyarlamali"
            d.ortak["kisa-oyku"] = ["flash"]
        s.cikislar = [Cikis.KOTA, Cikis.TAMAM]
        s.teslimler = [TeslimDurumu.KONULDU]
        s.zamanlayici(gunluk=(10, 10, 0)).calis(tur_siniri=4)
        self.assertEqual([i.model for i in s.isler], ["lite", "flash"])
        self.assertEqual(s.isler[1].ortak, ("lite",))

    def test_guvenlik_reddi_eseri_aractan_alir(self):
        s = Sahne(self, {"kisa-oyku": 1000})
        s.cikislar = [Cikis.GUVENLIK, Cikis.TAMAM]
        s.teslimler = [TeslimDurumu.KONULDU]
        s.zamanlayici().calis(tur_siniri=4)
        self.assertEqual([i.model for i in s.isler], ["lite", "flash"])
        self.assertEqual(s.depo.oku().ret, {"lite": ["kisa-oyku"]})

    def test_gecici_sorun_eseri_aractan_almaz(self):
        s = Sahne(self, {"kisa-oyku": 1000})
        s.cikislar = [Cikis.GECICI, Cikis.GECICI, Cikis.GECICI, Cikis.TAMAM]
        s.teslimler = [TeslimDurumu.KONULDU]
        s.zamanlayici().calis(tur_siniri=6)
        self.assertEqual([i.model for i in s.isler], ["lite"] * 4)
        self.assertEqual(s.depo.oku().ret, {})

    def test_iki_beklenmeyen_hata_eseri_aractan_alir(self):
        s = Sahne(self, {"kisa-oyku": 1000})
        s.cikislar = [Cikis.HATA, Cikis.HATA, Cikis.KOTA, Cikis.KOTA]
        s.zamanlayici(gunluk=(10, 10, 0)).calis(tur_siniri=4)
        self.assertEqual(s.depo.oku().ret, {"lite": ["kisa-oyku"]})

    def test_kontrolden_gecmeyen_once_onarilir_sonra_birakilir(self):
        s = Sahne(self, {"kisa-oyku": 1000})
        s.cikislar = [Cikis.TAMAM, Cikis.TAMAM, Cikis.KOTA, Cikis.KOTA]
        s.teslimler = [TeslimDurumu.KONTROLDEN_GECMEDI, TeslimDurumu.KONTROLDEN_GECMEDI]
        s.zamanlayici(gunluk=(10, 10, 0)).calis(tur_siniri=4)
        self.assertEqual(s.silinen, 1)
        self.assertTrue(any(k.startswith("ONARIM") for k in s.kayitlar))
        self.assertEqual(s.depo.oku().ret, {"lite": ["kisa-oyku"]})
        self.assertEqual([i.model for i in s.isler], ["lite", "lite", "flash"])

    def test_sabit_bloklu_arac_yalniz_kendi_esereni_okur(self):
        s = Sahne(self, {"kisa-oyku": 1000})
        with s.depo.degistir() as d:
            d.atama["kisa-oyku"] = "k31"
            d.yontem["kisa-oyku"] = "eski"
        s.cikislar = [Cikis.TAMAM]
        s.teslimler = [TeslimDurumu.KONULDU]
        s.zamanlayici(gunluk=(0, 0, 10)).calis(tur_siniri=3)
        self.assertEqual((s.isler[0].model, s.isler[0].sabit_blok, s.isler[0].hedef_sn), ("k31", 2000, None))

    def test_onceki_atamalar_kuyrukta_olmayan_eserden_temizlenir(self):
        s = Sahne(self, {"kisa-oyku": 1000})
        with s.depo.degistir() as d:
            d.atama["eski-eser"] = "lite"
        s.cikislar = [Cikis.TAMAM]
        s.teslimler = [TeslimDurumu.KONULDU]
        s.zamanlayici().calis(tur_siniri=1)
        self.assertNotIn("eski-eser", s.depo.oku().atama)


class DagitimTesti(unittest.TestCase):
    def test_en_uzun_eser_en_bos_araca(self):
        from sesli.durum import Durum
        araclar = [Z.AracDurumu(LITE, 10, kapasite=200), Z.AracDurumu(FLASH, 10, kapasite=100),
                   Z.AracDurumu(K31, 10, kapasite=100)]
        plan = Z.dagit(araclar, Durum(), {"a": 400, "b": 100, "c": 100})
        self.assertEqual(plan, {"lite": ["a"], "flash": ["b", "c"], "k31": []})

    def test_ret_edilen_araca_verilmez(self):
        from sesli.durum import Durum
        araclar = [Z.AracDurumu(LITE, 10, kapasite=100), Z.AracDurumu(FLASH, 10, kapasite=100)]
        plan = Z.dagit(araclar, Durum(ret={"lite": ["a"]}), {"a": 100})
        self.assertEqual(plan, {"lite": [], "flash": ["a"]})

    def test_kota_yenilenme_kis_ve_yaz_saati(self):
        self.assertEqual(Z.kota_yenilenme(dt.datetime(2026, 11, 5, 3, 0).astimezone()).hour, 11)  # kış: TR 11:05
        self.assertEqual(Z.kota_yenilenme(dt.datetime(2026, 7, 5, 3, 0).astimezone()).hour, 10)   # yaz: TR 10:05

    def test_duvar_saatiyle_bekle(self):
        saat = [dt.datetime(2026, 1, 1, 0, 0)]
        uykular = []

        def uyu(sn):
            uykular.append(sn)
            saat[0] += dt.timedelta(seconds=sn * 30)  # Mac uyudu: duvar saati uykudan çok ilerledi

        Z.duvar_saatiyle_bekle(dt.datetime(2026, 1, 1, 1, 0), uyu=uyu, simdi=lambda: saat[0])
        self.assertLessEqual(len(uykular), 3)


class HedefSureTesti(GeciciKokTesti):
    def test_olcum_yoksa_varsayilan(self):
        self.assertEqual(Z.hedef_sn("gemini-3.8-flash-tts", self.y), Z.VARSAYILAN_HEDEF)

    def test_aile_olcumunden(self):
        self.y.sinir.write_text('{"gemini-3.8-flash-lite-tts": {"sn": 1233, "durum": "tam"}}')
        self.assertEqual(Z.hedef_sn("gemini-3.8-flash-tts", self.y), 1134)


if __name__ == "__main__":
    unittest.main()


class CanliAlarmTesti(GeciciKokTesti):
    """Bugün kota harcayıp ses getirmeyen istekler sınıra ulaşırsa okuma o gün durur (H-001 türü bir sorun canlıda
    yakalanır)."""

    def test_israf_sinira_ulasinca_okuma_durur_kota_yenilenince_surer(self):
        s = Sahne(self, {"kisa-oyku": 1000})
        bosa = [Z.ISRAF_SINIRI, 0]
        s.b.bosa_giden = lambda: bosa.pop(0) if bosa else 0
        s.cikislar = [Cikis.TAMAM]
        s.teslimler = [TeslimDurumu.KONULDU]
        s.zamanlayici().calis(tur_siniri=5)
        self.assertTrue(any(k.startswith("ALARM") for k in s.kayitlar))
        self.assertEqual(len(s.beklemeler), 1, "alarm günü kota yenilenene dek beklenmeli")
        self.assertEqual(len(s.isler), 1, "ertesi gün okuma sürmeli")

    def test_sinirin_altinda_okuma_surer(self):
        s = Sahne(self, {"kisa-oyku": 1000})
        s.b.bosa_giden = lambda: Z.ISRAF_SINIRI - 1
        s.cikislar = [Cikis.TAMAM]
        s.teslimler = [TeslimDurumu.KONULDU]
        s.zamanlayici().calis(tur_siniri=5)
        self.assertFalse(any(k.startswith("ALARM") for k in s.kayitlar))
        self.assertEqual((len(s.isler), s.beklemeler), (1, []))


class BosaGidenTesti(GeciciKokTesti):
    def test_yalniz_kota_harcayip_ses_getirmeyenler_sayilir(self):
        from sesli.kota import kota_gunu
        import json as _json
        simdi = dt.datetime.now().astimezone()
        zaman = simdi.strftime("%Y-%m-%dT%H:%M:%S%z")
        sonuclar = ["ses", "ses", "kayip", "zaman_asimi", "bos", "guvenlik", "hata", "gitmedi", "sinir"]
        self.y.istek_defteri.write_text("".join(_json.dumps({"zaman": zaman, "sonuc": x}) + "\n" for x in sonuclar))
        self.assertEqual(kota_gunu(simdi), kota_gunu())
        self.assertEqual(Z.bosa_giden(self.y), 5)


class SorunluBlokSilmeTesti(GeciciKokTesti):
    """Onarım için yalnız sorunlu blokların önbelleği silinir: sağlam blok silinirse yeniden okunur, kota boşa gider."""

    def setUp(self):
        super().setUp()
        self.fola = self.y.fola_klasoru("kisa-oyku")
        self.fola.mkdir(parents=True)
        self.dosyalar = {no: self.y.parcalar / f"blok-{no}.wav" for no in range(1, 6)}
        for d in self.dosyalar.values():
            d.write_bytes(b"ses")
        plan = [{"no": no, "dosya": d.name} for no, d in self.dosyalar.items()] + [{"no": 6, "tarz": "sessizlik"}]
        (self.fola / "plan.json").write_text(json.dumps(plan))

    def _kontrol(self, bloklar):
        rapor = [{"no": no, "oran": oran, "kapsama": 1.0, "metin": "", "duyulan": "", "atlama": atlama}
                 for no, oran, atlama in bloklar]
        (self.fola / "kontrol.json").write_text(json.dumps({"eslesme": 98.0, "bloklar": rapor}))

    def _kalanlar(self):
        return sorted(no for no, d in self.dosyalar.items() if d.exists())

    def test_yalniz_atlamali_dusuk_ve_bozuk_bloklar_silinir(self):
        self._kontrol([(1, 0.99, []), (2, 0.98, ["atlanan cümle"]), (3, 0.89, []), (4, 0.90, []), (5, 0.99, [])])
        (self.fola / "kalite.json").write_text(json.dumps([{"no": n, "bozuk": n == 5} for n in range(1, 6)]))
        self.assertEqual(Z.sorunlu_bloklari_sil("kisa-oyku", self.y), 3)
        self.assertEqual(self._kalanlar(), [1, 4], "0,90 tam eşikte ve sağlam bloklar kalmalı")

    def test_kalite_kaydi_bozuksa_yalniz_kontroldekiler_silinir(self):
        self._kontrol([(1, 0.99, []), (2, 0.5, [])])
        (self.fola / "kalite.json").write_text("{bozuk")
        self.assertEqual(Z.sorunlu_bloklari_sil("kisa-oyku", self.y), 1)
        self.assertEqual(self._kalanlar(), [1, 3, 4, 5])

    def test_plan_yoksa_ya_da_bozuksa_hicbir_sey_silinmez(self):
        self._kontrol([(1, 0.1, ["x"])])
        (self.fola / "plan.json").unlink()
        self.assertEqual(Z.sorunlu_bloklari_sil("kisa-oyku", self.y), 0)
        (self.fola / "plan.json").write_text("[bozuk")
        self.assertEqual(Z.sorunlu_bloklari_sil("kisa-oyku", self.y), 0)
        self.assertEqual(self._kalanlar(), [1, 2, 3, 4, 5])

    def test_kontrol_kaydi_yoksa_yalniz_bozuk_sesli_bloklar_silinir(self):
        (self.fola / "kalite.json").write_text(json.dumps([{"no": 4, "bozuk": True}, {"no": 2, "bozuk": False}]))
        self.assertEqual(Z.sorunlu_bloklari_sil("kisa-oyku", self.y), 1)
        self.assertEqual(self._kalanlar(), [1, 2, 3, 5])

    def test_dosyasi_zaten_olmayan_blok_sayilmaz(self):
        self._kontrol([(2, 0.5, []), (3, 0.5, [])])
        self.dosyalar[2].unlink()
        self.assertEqual(Z.sorunlu_bloklari_sil("kisa-oyku", self.y), 1)


class HedefSureVeKapasiteTesti(GeciciKokTesti):
    """Blok boyu (hedef ses süresi) ölçülen sınırlardan: büyük olursa model keser, küçük olursa istek boşa gider."""

    def sinir(self, kayit):
        self.y.sinir.write_text(json.dumps(kayit))

    def test_olcum_yoksa_varsayilan_aile_var_ama_sonuc_yoksa_540(self):
        self.assertEqual(Z.hedef_sn("gemini-3.8-flash-tts", self.y), Z.VARSAYILAN_HEDEF)
        self.sinir({"gemini-3.8-flash-tts": {"sn": 900, "durum": "bilinmiyor"}})
        self.assertEqual(Z.hedef_sn("gemini-3.8-flash-tts", self.y), 540)

    def test_tam_okunanin_yuzde_92si_sinirlar_icinde(self):
        for tam, beklenen in ((1233, 1134), (500, Z.VARSAYILAN_HEDEF), (2000, Z.EN_UZUN_HEDEF)):
            self.sinir({"gemini-3.8-flash-lite-tts": {"sn": tam, "durum": "tam"},
                        "gemini-3.8-flash-tts": {"sn": 100, "durum": "tam"}})
            self.assertEqual(Z.hedef_sn("gemini-3.8-flash-tts", self.y), beklenen, tam)

    def test_yalniz_kesik_olcum_varsa_en_kisasinin_yuzde_88i_en_az_470(self):
        self.sinir({"gemini-2.5-flash-preview-tts": {"sn": 1000, "durum": "kesik"},
                    "gemini-2.5-pro-tts": {"sn": 1200, "durum": "kesik"}})
        self.assertEqual(Z.hedef_sn("gemini-2.5-flash-preview-tts", self.y), 880)
        self.sinir({"gemini-2.5-flash-preview-tts": {"sn": 400, "durum": "kesik"}})
        self.assertEqual(Z.hedef_sn("gemini-2.5-flash-preview-tts", self.y), 470)

    def test_baska_ailenin_olcumu_kullanilmaz(self):
        self.sinir({"gemini-2.5-flash-preview-tts": {"sn": 1233, "durum": "tam"}})
        self.assertEqual(Z.hedef_sn("gemini-3.8-flash-tts", self.y), Z.VARSAYILAN_HEDEF)

    def test_bozuk_sinir_kaydi_varsayilana_doner(self):
        self.y.sinir.write_text("{bozuk")
        self.assertEqual(Z.hedef_sn("gemini-3.8-flash-tts", self.y), Z.VARSAYILAN_HEDEF)

    def test_kapasite_ve_kurulum(self):
        from sesli import olcum
        lite, flash, k31 = Z.ARACLAR
        self.assertEqual(Z.kapasite(k31, self.y), Z.SABIT_KAPASITE)
        self.assertEqual(Z.kapasite(lite, self.y), Z.GUNLUK_ISTEK * Z.VARSAYILAN_HEDEF * olcum.VARSAYILAN_HIZ * 0.8)
        self.y.olcum.write_text("".join(json.dumps({"model": lite.model, "iyi": False}) + "\n" for _ in range(10)))
        self.assertEqual(Z.kapasite(lite, self.y), Z.GUNLUK_ISTEK * Z.VARSAYILAN_HEDEF * olcum.VARSAYILAN_HIZ * 0.4,
                         "başarı oranı ne kadar düşük olursa olsun en az 0,4 sayılır")
        z = Z.kur(self.y, {lite.model: 0, k31.model: 3})
        self.assertEqual([(a.model, a.gunluk) for a in z.araclar],
                         [(lite.model, 0), (flash.model, Z.GUNLUK_ISTEK), (k31.model, 3)])
        self.assertEqual(z.araclar[2].kapasite, Z.SABIT_KAPASITE)
