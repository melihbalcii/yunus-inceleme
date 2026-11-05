from __future__ import annotations

import contextlib
import io
import json
import unittest

from testler.yardim import GeciciKokTesti, SahteTTS
from sesli import cli
from sesli import gemini as G
from sesli.isci import Cikis, IsTanimi, oku_eser


def _is(**k) -> IsTanimi:
    v = dict(ad="kisa-oyku", arac_adi="Gemini 3.8 Flash TTS", model="m", ses="Fola", ortak=("m2",),
             hedef_sn=600, sabit_blok=None) | k
    return IsTanimi(**v)


class CikisTesti(unittest.TestCase):
    def test_bilinmeyen_kod_hata(self):
        self.assertIs(Cikis.koddan(75), Cikis.KOTA)
        self.assertIs(Cikis.koddan(-9), Cikis.HATA)  # öldürülen süreç

    def test_is_tanimi_komut_satirindan_aynen_doner(self):
        for is_ in (_is(), _is(ortak=(), hedef_sn=None, sabit_blok=2000)):
            a = cli.ayristirici().parse_args(is_.arguman())
            geri = IsTanimi(ad=a.ad, arac_adi=a.arac_adi, model=a.model, ses=a.ses,
                            ortak=tuple(m for m in (a.ortak or "").split(",") if m),
                            hedef_sn=a.hedef_sn, sabit_blok=a.sabit_blok)
            self.assertEqual(geri, is_)


class IsciTesti(GeciciKokTesti):
    def calistir(self, hata: BaseException) -> Cikis:
        self.metin_yaz("kisa-oyku", ["Tek paragraf."])
        with contextlib.redirect_stdout(io.StringIO()):
            return oku_eser(_is(), self.y, tts_kur=lambda arac, y, bildir: SahteTTS([hata]))

    def test_hatalar_cikis_koduna_cevrilir(self):
        self.assertIs(self.calistir(G.KotaDoldu("x")), Cikis.KOTA)
        self.assertIs(self.calistir(G.GuvenlikReddi(10)), Cikis.GUVENLIK)
        self.assertIs(self.calistir(G.GeciciHata("x")), Cikis.GECICI)
        self.assertIs(self.calistir(G.BosYanit("x")), Cikis.BOLUNEMEZ)
        self.assertIs(self.calistir(ValueError("beklenmeyen")), Cikis.HATA)


class CliTesti(GeciciKokTesti):
    def calistir(self, *arg: str) -> tuple[int, str]:
        cikti, uyari = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(cikti), contextlib.redirect_stderr(uyari):
            kod = cli.main(list(arg), yollar=self.y)
        return kod, cikti.getvalue() + uyari.getvalue()

    def test_durum(self):
        self.metin_yaz("kisa-oyku", ["kısa"])
        self.y.durum.write_text(json.dumps({"atama": {"kisa-oyku": "m1"}, "ortak": {"kisa-oyku": ["m2"]}}))
        kod, cikti = self.calistir("durum")
        self.assertEqual(kod, 0)
        self.assertIn("okunuyor: m1 + m2", cikti)
        self.assertIn("okunmayacak", cikti)  # Emel kopyası olmayan eser
        self.assertIn("Kuyruk (kısadan uzuna): kisa-oyku", cikti)

    def test_hazirla(self):
        self.metin_yaz("kisa-oyku", ["Bir.", "İki."])
        kod, _ = self.calistir("hazirla", "kisa-oyku")
        self.assertEqual(kod, 0)
        self.assertTrue((self.y.fola_klasoru("kisa-oyku") / "seslendirme-metni.txt").exists())

    def test_teslim_kayit_yoksa_bildirir(self):
        kod, cikti = self.calistir("teslim", "kisa-oyku")
        self.assertEqual(kod, 1)
        self.assertIn("okuma kaydı yok", cikti)

    def test_bilinmeyen_komut(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main(["yok"], yollar=self.y)


if __name__ == "__main__":
    unittest.main()
