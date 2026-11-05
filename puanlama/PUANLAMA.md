# Puanlama sistemi

Bu depodaki kod bağımsız araçlarla ölçülür. Puanı kodu yazan kişi ya da yapay zekâ vermez. Formül ve eşikler
ilk ölçümden **önce** yazılıp kayda geçirildi (bu dosyanın git geçmişi bunu gösterir); sonradan değiştirilmez.
Bir değişiklik gerekirse ayrı bir kayıtla, gerekçesiyle ve eski formülle hesaplanmış puan yanında yapılır.

Hesaplama: `puanlama/puan.py`, araçların ham çıktılarını (`puanlama/sonuclar/*.json`) okur.

## Kesin şartlar (biri bile tutmazsa sonuç "GEÇMEDİ", puan ne olursa olsun)

| Şart | Araç |
|---|---|
| 0 tip hatası | mypy (strict), deno check |
| 0 katman ihlali | import-linter |
| 0 yüksek ya da kritik güvenlik bulgusu | CodeQL, bandit (yüksek önem) |
| Açığı bilinen 0 bağımlılık | pip-audit, npm audit |
| Bütün testler geçer | unittest, node --test |

## 100 puan, 5 alan

Her alt ölçüm 0–100 arasıdır; alan puanı alt ölçümlerin ağırlıklı ortalaması × alan ağırlığıdır.
Ölçülemeyen alt ölçüm 0 sayılır ve raporda "ÖLÇÜLMEDİ" diye yazılır (eksik ölçüm puanı şişirmez).

### 1. Doğruluk ve hata dayanıklılığı — 35 puan
| Alt ölçüm | Pay | Hesap |
|---|---|---|
| Mutasyon puanı (Python, mutmut) | %45 | öldürülen ÷ (toplam − atlanan) × 100 |
| Mutasyon puanı (TypeScript, StrykerJS) | %15 | Stryker'ın "mutation score" değeri |
| Dal kapsamı (Python, coverage.py `--branch`) | %25 | yüzde |
| Satır kapsamı (TypeScript, `node --test --experimental-test-coverage`) | %15 | yüzde |

### 2. Mimari — 20 puan
| Alt ölçüm | Pay | Hesap |
|---|---|---|
| Katman kuralları (import-linter) | %40 | tutulan sözleşme ÷ toplam sözleşme × 100 |
| İşlev karmaşıklığı (ruff C901, sınır 10) | %40 | 100 × (1 − sınırı aşan işlev ÷ toplam işlev) |
| Modül boyutu | %20 | 100 × (1 − 400 satırı aşan modül ÷ toplam modül); JS/TS dahil |

### 3. Kod kalitesi — 15 puan
| Alt ölçüm | Pay | Hesap |
|---|---|---|
| SonarQube Cloud güvenilirlik ve bakım notları | %50 | A=100, B=80, C=60, D=40, E=20; iki notun ortalaması |
| SonarQube Cloud kod tekrarı | %20 | max(0, 100 − 10 × tekrar yüzdesi) |
| Kural ihlali yoğunluğu (ruff) | %30 | max(0, 100 − 10 × (ihlal ÷ 1000 satır)) |

ruff kural kümesi: `E, F, W, B, C90, UP, SIM, PL` (satır sınırı 120). Kümeyi daraltmak puanı şişirmek sayılır.

### 4. Güvenlik — 15 puan
| Alt ölçüm | Pay | Hesap |
|---|---|---|
| bandit | %40 | max(0, 100 − 25 × yüksek − 10 × orta − 2 × düşük) |
| Bağımlılık açıkları (pip-audit + npm audit) | %30 | max(0, 100 − 20 × açık sayısı) |
| OpenSSF Scorecard | %30 | toplam puan × 10 |

### 5. Ön yüz — 15 puan
| Alt ölçüm | Pay | Hesap |
|---|---|---|
| Lighthouse: performans | %20 | kategori puanı |
| Lighthouse: erişilebilirlik | %20 | kategori puanı |
| Lighthouse: iyi uygulamalar | %20 | kategori puanı |
| axe (Playwright ile, giriş ve ana sayfa) | %20 | max(0, 100 − 15 × ciddi/kritik ihlal − 5 × diğer ihlal) |
| Ön yüz test kapsamı (Playwright, `uygulama.js` satır kapsamı) | %20 | yüzde |

## Notlar

- Testler bu ölçümlere göre "ayarlanmaz": bir mutasyonu öldürmek için yazılan test gerçek bir davranışı sınamalıdır.
  `pragma: no mutate` ve kapsam dışı bırakma yorumları her kullanımda gerekçesiyle `puanlama/ISTISNALAR.md`'ye yazılır.
- Araç sürümleri `araclar/gereksinimler-olcum.txt` ve `kitaplik/package.json`'da sabittir.

## Açıklamalar (5 Kasım 2026, ilk puan hesaplanmadan önce eklendi)

- **axe "ihlal" sayısı:** Etkilenen öğe başına sayılır (bir kural 20 öğede bozulduysa 20 ihlal). Kural başına sayım
  daha yumuşak olurdu; axe sonucu bu açıklamadan önce görüldüğü için sert olan yorum seçildi.
- **npm audit:** Sitenin çalışırken kullandığı paketler (`npm audit --omit=dev`). Ölçüm ve yayın araçları
  (Lighthouse, Stryker, netlify-cli) siteye girmez. pip-audit de yalnız `araclar/gereksinimler.txt`'i (üretim
  sisteminin kütüphaneleri) tarar.
- **Lighthouse kategori puanı:** Her sayfa 3 kez ölçülür, ortanca alınır; iki sayfanın ortalaması kullanılır.
- **Mutasyon puanında zaman aşımı:** Stryker'ın ve mutmut'un "timeout" sonucu öldürülmüş sayılır (iki aracın da
  varsayılanı).

## Değişiklikler

### v2 — 6 Kasım 2026: "Dayanıklılık" ayrı alan (10 puan)
**Gerekçe:** Yunus'un bulduğu sorun (H-001: hata durumunda aynı işin 2–4 kez yaptırılması) v1'deki hiçbir ölçümle
yakalanmıyordu. Hata durumlarını gerçek koşulda sınayan testler artık var; puanda ayrı görünmeleri gerekir.

| Alan | v1 | v2 |
|---|---|---|
| Doğruluk (alt ölçümler aynı) | 35 | 30 |
| Mimari | 20 | 17 |
| Kod kalitesi | 15 | 14 |
| Güvenlik | 15 | 14 |
| Ön yüz | 15 | 15 |
| Dayanıklılık | — | 10 |

Dayanıklılık alt ölçümleri: gerçek ağ arızası (Toxiproxy, `testler/test_ag_kopmasi.py`) %35, çökme (süreç öldürme,
`testler/test_cokme.py`) %35, rastgele hata sırası (Hypothesis + başvuru modeli, `testler/test_dayaniklilik.py`) %30.
Her biri geçen test ÷ toplam; atlanan test (ör. Toxiproxy yok) geçmemiş sayılır. Bu alan "sınama yapılıyor ve
geçiyor" der; testlerin gücünü mutasyon puanı (Doğruluk) ölçer. Her rapor v1 formülüyle hesaplanan puanı da yazar.
