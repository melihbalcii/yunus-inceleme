# Sesli kitap sistemi

[![Puanlama](https://github.com/melihbalcii/yunus-inceleme/actions/workflows/puanlama.yml/badge.svg)](https://github.com/melihbalcii/yunus-inceleme/actions/workflows/puanlama.yml)

Kod bağımsız araçlarla puanlanır (mutasyon testi, kapsam, katman kuralları, SonarQube, CodeQL, OpenSSF Scorecard,
Lighthouse, axe). Formül ve eşikler ilk ölçümden önce yazıldı: [puanlama/PUANLAMA.md](puanlama/PUANLAMA.md).
Son puan: Actions sekmesinde "Puanlama" işinin özeti. Yerelde: `PY=python3.11 bash puanlama/olc.sh`.

Kişisel bir sesli kitap arşivi: üretim sistemi, site sunucusu ve site ön yüzü.

| Klasör | Ne yapar |
|---|---|
| `araclar/` (Python 3.11) | Eserleri Gemini TTS ile blok blok seslendirir. Her bloğu Whisper ile metne karşı denetler, eksik okunan yeri yamalar ya da yeniden okutur. Günlük kotaları üç model arasında paylaştırır, sonunda tek MP3 teslim eder. |
| `kitaplik/netlify/` (TypeScript, Netlify Edge) | Sitenin şifre kapısı: ortak şifre ve HMAC imzalı oturum çerezi. |
| `kitaplik/public/` (HTML, CSS, JS) | Sitenin ön yüzü: sesli kitap çalar. Fotoğraflı görseller bu kopyada yer tutucuyla değiştirildi. |

Mimari, katmanlar, değişmezler ve hata modeli `araclar/sesli/MIMARI.md` içinde. İlk okunacak dosya o.

## Çalıştırma

```sh
cd araclar
python -m unittest discover -s testler -t . -p "test_*.py"   # 109 birim testi (numpy, lameenc gerekir)
python -m mypy                                               # strict tip denetimi (ayarı: mypy.ini)

cd ../kitaplik
npm test                                                     # şifre kapısının 11 testi (Node 22+)
```

## Kopyaya dahil olmayanlar

- Gizli bilgiler (`.env`: API anahtarı, site şifresi), eser metinleri, ses önbelleği ve yayın dosyaları.
- `testler/uyumluluk.py`, yeni kodu eski betiklerle gerçek veri üzerinde karşılaştırır. Bu kopyada o veri olmadığı için testleri atlanır.
- `araclar/eski/`: yeniden yazımdan önceki 27 betik. İncelenecek kodun parçası değil.

## Geçmiş

Bu kod 5 Kasım 2026'da baştan yazıldı. Eski sistemle aynı çıktıyı verdiği gerçek bir eserde doğrulandı: aynı girdilerle üretilen 360 MB'lık MP3 bayt bayt aynı çıktı.
