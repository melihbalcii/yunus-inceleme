"""Sesli kitap üretim sistemi.

Akış: eser listesi (podcast/eserler.json) → okuma metni (podcast/<eser>/fola/seslendirme-metni.txt) → Gemini TTS ile
blok blok okuma (zamanlayici + isci) → Whisper ve ses kalitesi kontrolü (kontrol) → teslim klasörüne koyma (teslim)
→ site yayın klasörü (site).

Bütün yollar `yollar.Yollar`'da, eser bilgileri `katalog.Katalog`'da, okuma durumu `durum.DurumDeposu`'nda tutulur;
modüller birbirinin dosyasını ayrıştırmaz. Komut satırı: .venv-ses/bin/python araclar/sesli_kitap.py --help
"""
