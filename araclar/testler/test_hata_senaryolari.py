"""Hata durumlarında kota güvenliği (5 Kasım, Yunus'un incelemesi).

Her test, ATILAN İSTEK SAYISINI doğrular: bir hata aynı işin arka planda ikinci kez yaptırılmasına, okunmuş bir sesin
çöpe gitmesine ya da iki sürecin aynı eseri okumasına yol açmamalı.
"""
from __future__ import annotations

import threading
import time
import unittest

import httpx
import numpy as np

from testler.test_gemini import _tts, _wav, _yanit
from testler.yardim import GeciciKokTesti, SahteTTS, ses
from sesli import cli
from sesli import gemini as G
from sesli import okuma as O
from sesli import zamanlayici as Z
from sesli.isci import Cikis, IsTanimi, oku_eser
from sesli.kilit import ZatenCalisiyor, tek_kopya
from sesli.olcum import istek_ozeti
from sesli.teslim import TeslimDurumu
from testler.test_zamanlayici import Sahne


class SayanIstemci:
    """Aynı anda kaç istek çalıştığını da ölçen sahte Gemini istemcisi."""

    def __init__(self, davranislar):
        self.davranislar = list(davranislar)
        self.models = self
        self.cagri = 0
        self.ayni_anda = 0
        self.en_cok_ayni_anda = 0
        self._kilit = threading.Lock()

    def generate_content(self, **_):
        with self._kilit:
            self.cagri += 1
            self.ayni_anda += 1
            self.en_cok_ayni_anda = max(self.en_cok_ayni_anda, self.ayni_anda)
            d = self.davranislar.pop(0)
        try:
            if isinstance(d, BaseException):
                raise d
            return d() if callable(d) else d
        finally:
            with self._kilit:
                self.ayni_anda -= 1


def _gemini(istemci: SayanIstemci, **ayar) -> tuple[G.GeminiTTS, list[dict]]:
    defter: list[dict] = []
    t = G.GeminiTTS(G.Arac("Deneme TTS", "deneme-model", "Fola"), "anahtar", bildir=lambda s: None,
                    uyu=lambda s: None, istemci_kur=lambda: istemci, defter=defter.append, **ayar)
    return t, defter


def _gecikmeli(sn: float):
    def f():
        time.sleep(sn)
        return _yanit(_wav(0.1))
    return f


class GeminiIstegiTesti(unittest.TestCase):
    def test_gecikip_gelen_yanit_kullanilir_ikinci_istek_atilmaz(self):
        """Eskiden 15 dk dolunca istek bırakılıp yenisi atılıyordu: ikisi birden Gemini'de okunuyordu."""
        i = SayanIstemci([_gecikmeli(0.6), _yanit(_wav(0.1))])
        t, defter = _gemini(i, istek_suresi=0.1, en_uzun_bekleme=5)
        self.assertEqual(len(t.uret("metin")), 2400)
        self.assertEqual((i.cagri, t.atilan), (1, 1))
        self.assertEqual([k["sonuc"] for k in defter], ["ses"])

    def test_hic_donmeyen_istek_icin_yeni_istek_atilmaz(self):
        olay = threading.Event()
        i = SayanIstemci([lambda: (olay.wait(10), _yanit(_wav(0.1)))[1], _yanit(_wav(0.1))])
        t, defter = _gemini(i, istek_suresi=0.1, en_uzun_bekleme=0.4)
        with self.assertRaises(G.GeciciHata):
            t.uret("metin")
        # önceki istek hâlâ sürerken çağrılırsa da ikinci istek atılmaz
        with self.assertRaisesRegex(G.GeciciHata, "önceki istek"):
            t.uret("metin")
        self.assertEqual((i.cagri, i.en_cok_ayni_anda), (1, 1))
        self.assertEqual([k["sonuc"] for k in defter], ["zaman_asimi"])
        olay.set()

    def test_baglanilamayan_istek_kota_harcamadan_yinelenir(self):
        i = SayanIstemci([httpx.ConnectError("yok"), httpx.ConnectTimeout("yok"), _yanit(_wav(0.1))])
        t, defter = _gemini(i)
        t.uret("metin")
        self.assertEqual((i.cagri, t.atilan), (3, 1))
        self.assertEqual([k["sonuc"] for k in defter], ["gitmedi", "gitmedi", "ses"])

    def test_yaniti_kaybolan_istek_en_cok_butce_kadar(self):
        kayip = [httpx.ReadTimeout("geç"), httpx.RemoteProtocolError("yanıtsız kapandı"), _yanit(_wav(0.1))]
        i = SayanIstemci(kayip)
        t, defter = _gemini(i)
        with self.assertRaises(G.GeciciHata):
            t.uret("metin")  # varsayılan bütçe 2: ilk istek + bir tekrar; üçüncüsü atılmaz
        self.assertEqual((i.cagri, t.atilan), (2, 2))
        self.assertEqual([k["sonuc"] for k in defter], ["kayip", "kayip"])

        i = SayanIstemci([httpx.ReadTimeout("geç"), _yanit(_wav(0.1))])
        t, _ = _gemini(i)
        with self.assertRaises(G.GeciciHata):
            t.uret("metin", en_cok=1)
        self.assertEqual(i.cagri, 1)

    def test_bos_butceyle_hic_istek_atilmaz(self):
        i = SayanIstemci([_yanit(_wav(0.1))])
        t, _ = _gemini(i)
        with self.assertRaises(G.GeciciHata):
            t.uret("metin", en_cok=0)
        self.assertEqual(i.cagri, 0)

    def test_defter_ozeti_kota_gunune_gore_sayar(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as k:
            yol = Path(k) / "defter.jsonl"
            kayitlar = [{"zaman": "2026-11-05T12:00:00+0300", "sonuc": "ses"},
                        {"zaman": "2026-11-05T12:10:00+0300", "sonuc": "kayip"},
                        {"zaman": "2026-11-05T10:00:00+0300", "sonuc": "ses"}]  # Pasifik'te 4 Kasım
            yol.write_text("".join(json.dumps(x) + "\n" for x in kayitlar))
            self.assertEqual(istek_ozeti(yol, "2026-11-05"), {"ses": 1, "kayip": 1})
            self.assertEqual(istek_ozeti(yol, "2026-11-04"), {"ses": 1})


class OkuyucuKotaTesti(GeciciKokTesti):
    METIN = "Birinci paragraf burada.\n\nİkinci paragraf da burada."

    def okuyucu(self, tts, olc, yamala=None, gun="2026-11-05"):
        a = O.OkumaAyari(model="m1", ses="Fola", hedef_sn=60)
        self.mesajlar: list[str] = []
        return O.Okuyucu(tts, a, self.y, bildir=self.mesajlar.append, olc=olc, kalite=lambda s: (3.6, 3.5),
                         yamala=yamala or (lambda *a, **k: None), gun=lambda: gun)

    def test_kota_ikinci_denemede_bitince_ilk_deneme_kaybolmaz(self):
        """Günlükte: 18 dk'lık ses okundu, sonra kota bitti, ses kayboldu; ertesi gün yeniden okundu."""
        dun = SahteTTS([None, G.KotaDoldu("bitti")])
        with self.assertRaises(G.KotaDoldu):
            self.okuyucu(dun, olc=lambda m, s: (0.80, []))._blok(self.METIN, "[1]")
        self.assertEqual(dun.atilan, 1)
        bugun = SahteTTS()
        _, sonuc = self.okuyucu(bugun, olc=lambda m, s: (0.99, []), gun="2026-11-06")._blok(self.METIN, "[1]")
        self.assertEqual(len(bugun.istekler), 1)  # yalnız 2. deneme; 1. deneme diskten
        self.assertTrue(any("kayıtlı deneme" in m for m in self.mesajlar))
        self.assertEqual(sorted(p.name for p in self.y.parcalar.iterdir()),
                         [O.blok_dosyasi(self.y.parcalar, self.METIN, O.OkumaAyari("m1", "Fola")).name])

    def test_yama_isteginde_kota_bitince_blok_sesi_kaybolmaz(self):
        def kotali_yama(metin, ses_, uret, *a, **k):
            uret("eksik cümle")
            return ses_
        dun = SahteTTS([None, G.KotaDoldu("bitti")])
        with self.assertRaises(G.KotaDoldu):
            self.okuyucu(dun, olc=lambda m, s: (0.90, []), yamala=kotali_yama)._blok(self.METIN, "[1]")
        bugun = SahteTTS()
        self.okuyucu(bugun, olc=lambda m, s: (0.90, []), gun="2026-11-06")._blok(self.METIN, "[1]")
        # 1. deneme diskten geldi; bugün 2 deneme + yamalar, ama 1. deneme yeniden istenmedi
        self.assertLessEqual(len(bugun.istekler), O.BLOK_TAVANI)
        self.assertTrue(any("kayıtlı deneme" in m for m in self.mesajlar))

    def test_bolunen_blokta_okunmus_yari_yeniden_istenmez(self):
        dun = SahteTTS([G.BosYanit("OTHER"), None, G.KotaDoldu("bitti")])
        with self.assertRaises(G.KotaDoldu):
            self.okuyucu(dun, olc=lambda m, s: (0.99, []))._blok(self.METIN, "[1]")
        bugun = SahteTTS()
        _, sonuc = self.okuyucu(bugun, olc=lambda m, s: (0.99, []), gun="2026-11-06")._blok(self.METIN, "[1]")
        # ne bütün blok (yine boş dönecekti) ne sol yarı: yalnız sağ yarı
        self.assertEqual(bugun.istekler, ["İkinci paragraf da burada."])
        self.assertGreater(len(sonuc), 0)

    def test_tek_paragraflik_blok_bos_yanitta_kalici_isaretlenmez(self):
        """Boş yanıt geçici olabilir: bölünemeyen blok "bölünecek" diye işaretlenip bir daha hiç denenmez hâle gelmemeli."""
        tek = "Tek paragraflık bir blok."
        with self.assertRaises(O.BolunemezHata):
            self.okuyucu(SahteTTS([G.BosYanit("OTHER")]), olc=lambda m, s: (0.99, []))._blok(tek, "[1]")
        ertesi = SahteTTS()
        self.okuyucu(ertesi, olc=lambda m, s: (0.99, []), gun="2026-11-06")._blok(tek, "[1]")
        self.assertEqual(ertesi.istekler, [tek])  # ertesi gün yeniden denendi ve okundu

    def test_blok_basina_istek_tavani_hic_asilmaz(self):
        class HepKayip(SahteTTS):
            def uret(self, metin, en_cok=2):
                self.istekler.append(metin)
                self.atilan += en_cok  # bütçenin tamamı yanıtı kaybolan isteklere gitti
                raise G.GeciciHata("yanıt alınamadı")
        tts = HepKayip()
        for _ in range(5):  # zamanlayıcı aynı gün tekrar tekrar denese de
            with self.assertRaises(G.GeciciHata):
                self.okuyucu(tts, olc=lambda m, s: (0.99, []))._blok(self.METIN, "[1]")
        self.assertEqual(tts.atilan, O.BLOK_TAVANI)
        # kota günü değişince blok yeniden denenebilir (kesinti bloğu kalıcı kilitlemez)
        self.okuyucu(SahteTTS(), olc=lambda m, s: (0.99, []), gun="2026-11-06")._blok(self.METIN, "[1]")

    def test_hep_kotu_okunan_ve_yamasi_tutmayan_blok_tavani_asmaz(self):
        tts = SahteTTS()
        self.okuyucu(tts, olc=lambda m, s: (0.90, []),
                     yamala=lambda metin, ses_, uret, *a, **k: (uret("yama"), None)[1])._blok(self.METIN, "[1]")
        self.assertEqual(tts.atilan, O.BLOK_TAVANI)  # deneme, yama, deneme, yama: sonra en iyisi tutulur

    def test_her_istekte_butce_kalan_hakla_sinirli(self):
        tts = SahteTTS()
        self.okuyucu(tts, olc=lambda m, s: (0.80, []))._blok(self.METIN, "[1]")
        self.assertEqual(tts.butceler, [2, 2, 2])  # 3 deneme; tavan 4: son istekte kalan 2
        self.assertLessEqual(tts.atilan, O.BLOK_TAVANI)


class TekKopyaTesti(GeciciKokTesti):
    def test_ikinci_zamanlayici_baslamaz(self):
        with tek_kopya(self.y.zamanlayici_kilidi):
            self.assertEqual(cli.main(["oku"], self.y), 1)

    def test_kilit_birakilinca_yeniden_alinir(self):
        with tek_kopya(self.y.zamanlayici_kilidi):
            with self.assertRaises(ZatenCalisiyor):
                with tek_kopya(self.y.zamanlayici_kilidi):
                    pass
        with tek_kopya(self.y.zamanlayici_kilidi):
            pass

    def test_ayni_eseri_iki_surec_okuyamaz(self):
        is_ = IsTanimi("kisa-oyku", "Deneme TTS", "m1", "Fola", (), 60, None)
        kuruldu: list[int] = []
        with tek_kopya(self.y.eser_kilidi("kisa-oyku")):
            cikis = oku_eser(is_, self.y, tts_kur=lambda *a: kuruldu.append(1) or SahteTTS())
        self.assertIs(cikis, Cikis.GECICI)
        self.assertEqual(kuruldu, [])  # Gemini istemcisi hiç kurulmadı


class ZamanlayiciGeciciTesti(GeciciKokTesti):
    def test_ust_uste_gecici_sorunda_arac_dinlenir(self):
        s = Sahne(self, {"kisa-oyku": 1000})
        s.cikislar = [Cikis.GECICI] * Z.GECICI_SINIRI + [Cikis.TAMAM]
        s.teslimler = [TeslimDurumu.KONULDU]
        s.zamanlayici(gunluk=(10, 0, 0)).calis(tur_siniri=8)
        self.assertEqual(len(s.isler), Z.GECICI_SINIRI + 1)
        self.assertTrue(any("dinleniyor" in k for k in s.kayitlar))
        # dinlenme: kota yenilenmesine kadar beklenir, 10 dk'da bir yeni istek yakılmaz
        self.assertEqual(len(s.beklemeler), Z.GECICI_SINIRI)
        self.assertGreater(s.beklemeler[-1] - s.beklemeler[-2], Z.dt.timedelta(hours=1))


if __name__ == "__main__":
    unittest.main()
