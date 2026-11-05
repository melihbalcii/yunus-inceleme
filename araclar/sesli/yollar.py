"""Sistemin kullandığı bütün dosya ve klasör yolları tek yerde.

Testler `Yollar.kok_altinda(gecici_klasor)` ile her şeyi geçici bir klasöre yönlendirir; gerçek kod hep
`Yollar.varsayilan()` kullanır.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJE_KOKU = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Yollar:
    kok: Path
    teslim: Path         # ~/Desktop/sesli kitap fola: kontrolden geçen TTS kayıtları, araç alt klasörlerinde
    emel_teslim: Path    # ~/Desktop/sesli kitap: eski Emel'li kayıtlar (yalnız "bu eser tam mı" bilgisi için okunur)
    yayin: Path          # site yayın klasörü (iCloud'a gitmesin diye Masaüstü dışında)
    cop: Path            # silme yok: eskiyen teslim kopyaları buraya taşınır

    @classmethod
    def varsayilan(cls) -> Yollar:
        ev = Path.home()
        return cls(kok=PROJE_KOKU, teslim=ev / "Desktop" / "sesli kitap fola",
                   emel_teslim=ev / "Desktop" / "sesli kitap",
                   yayin=ev / "Library" / "Caches" / "melihten-dinle" / "yayin", cop=ev / ".Trash")

    @classmethod
    def kok_altinda(cls, kok: Path) -> Yollar:
        return cls(kok=kok, teslim=kok / "teslim", emel_teslim=kok / "emel-teslim", yayin=kok / "yayin",
                   cop=kok / "cop")

    # --- proje içi ---
    @property
    def podcast(self) -> Path:
        return self.kok / "podcast"

    @property
    def eserler(self) -> Path:
        return self.podcast / "eserler.json"

    @property
    def plan_csv(self) -> Path:
        return self.podcast / "klasikler-100.csv"

    @property
    def tmp(self) -> Path:
        return self.kok / ".tmp"

    @property
    def parcalar(self) -> Path:
        """Okunan blokların ses önbelleği (<özet>.wav) ve Whisper döküm önbelleği (yazidokum.json)."""
        return self.tmp / "gemini-parcalar"

    @property
    def durum(self) -> Path:
        return self.tmp / "fola-atama.json"

    @property
    def olcum(self) -> Path:
        return self.tmp / "fola-olcum.jsonl"

    @property
    def sinir(self) -> Path:
        return self.tmp / "fola-sinir.json"

    @property
    def gunluk(self) -> Path:
        return self.tmp / "fola-sirayla.log"

    @property
    def istek_defteri(self) -> Path:
        """Gemini'ye atılan her istek ve sonucu (gemini.GeminiTTS); boşa giden istekler buradan ölçülür."""
        return self.tmp / "istek-defteri.jsonl"

    @property
    def zamanlayici_kilidi(self) -> Path:
        return self.tmp / "zamanlayici.kilit"

    def eser_kilidi(self, ad: str) -> Path:
        return self.tmp / "kilit" / f"{ad}.kilit"

    @property
    def python(self) -> Path:
        return self.kok / ".venv-ses" / "bin" / "python"

    @property
    def gemini_env(self) -> Path:
        return self.kok / ".env"

    @property
    def kitaplik(self) -> Path:
        return self.kok / "kitaplik"

    def eser_klasoru(self, ad: str) -> Path:
        return self.podcast / ad

    def fola_klasoru(self, ad: str) -> Path:
        return self.podcast / ad / "fola"
