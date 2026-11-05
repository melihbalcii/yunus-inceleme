# Hata defteri

Bulunan her hata buraya yazılır. Amaç yalnız o hatayı değil, **o hata türünü** bir daha yaşamamak. Her kayıtta şu
sorunun cevabı vardır: "Bu türden bir hata tekrar olursa onu otomatik olarak ne yakalayacak?"

**Kaçan hata sayısı**, yani bizden önce başkasının bulduğu hata, her ay ayrıca sayılır. Hedef, bu sayının düşmesi.

| Ay | Bizden önce başkasının bulduğu | Araçların bulduğu | Bizim bulduğumuz |
|---|---|---|---|
| Kasım 2026 | 1 (Yunus: H-001) | 11 (H-004…H-012, H-014, H-015) | 3 (H-002, H-003, H-013) |

## Kayıtlar

### H-001 · Gemini isteği hata durumunda arka planda 2–4 kez yaptırılıyor
- **Bulan:** Yunus (insan incelemesi), 5 Kasım 2026 · **Önem:** yüksek (kota kaybı)
- **Tür:** Dış çağrıda istisnai durum (OWASP A10:2025) · Kontrol listesi D2, D3, D4
- **Kök neden:** Süre dolunca istek iptal edilmeden bırakılıp yenisi atılıyordu. Üç katman (istek, blok, eser) ayrı
  ayrı yeniden deniyordu, denemeler çarpılıyordu.
- **Neden kaçtı:** Testleri kodu yazan yazdı ve yalnız "her şey yolunda" durumunu sınadı. Kanıt okuma günlüğünde
  vardı, bakılmadı.
- **Tür denetimi:** Hata senaryosu testleri (istek sayısını doğrular); planlı: rastgele senaryo (Hypothesis),
  ağ arızası (Toxiproxy), canlı alarm.
- **Durum:** Düzeltme gerçek projede yazılıyor, henüz doğrulanmadı.

### H-002 · Kota bitince okunmuş ses kayboluyor
- **Bulan:** Okuma günlüğü (geriye dönük tarama), 5 Kasım 2026 · **Önem:** yüksek
- **Tür:** Yarıda kalma (K2, K3)
- **Kök neden:** Bir bloğun denemeleri diske yazılmadan bellekte tutuluyordu.
- **Gerçek zarar (araclar/haftalik_denetim.py ile bütün günlük tarandı):** 4 olay, 7 istek, ~85 dk ses kayboldu
  (26.10 Toprak 2 deneme, 26.10 Usher 2 deneme, 01.11 İdam Mahkûmu 1 deneme, 02.11 Dilin Âfetleri 2 deneme).
  Elle yalnız biri bulunmuştu.
- **Tür denetimi:** Deneme deposu ve testi; kayıt denetimi (haftalik_denetim.py "kaybolmuş olabilecek okuma");
  planlı: çökme testi.
- **Durum:** Düzeltme gerçek projede yazılıyor, henüz doğrulanmadı.

### H-003 · Okuma programı iki kez başlatılabiliyor
- **Bulan:** Biz (H-001 incelemesi sırasında) · **Önem:** orta · **Tür:** Aynı anda çalışma (E1)
- **Tür denetimi:** Tek kopya kilidi testi. **Durum:** Gerçek projede yazılıyor.

### H-004 · Sitede adres çubuğundan zararlı kod çalıştırma riski (DOM XSS)
- **Bulan:** SonarQube, 5 Kasım 2026 · **Önem:** engelleyici · **Tür:** OWASP A05, CWE-79 (G1)
- **Yer:** `kitaplik/public/uygulama.js` yonlendir(): adresten gelen değer `innerHTML` ile sayfaya yazılıyor.
- **Gerçek mi?** Evet: eski kodda depoya konan değer tarayıcıda kod olarak çalıştı (doğrulandı). Yol: "verilerimi
  içe aktar" ile kötü niyetli bir yedek dosyası. Kaynak `hedef` alanıydı; içe aktarma da hiçbir alanı denetlemiyordu.
- **Düzeltme:** Tek veri temizleyici (`temizle`): depodan okurken ve dosyadan içe aktarırken her alan türüne göre süzülür.
- **Tür denetimi:** SonarQube, CodeQL; `kitaplik/testler-tarayici/veri.test.mjs` (gerçek Chromium, 4 test; eski kodda 3'ü
  başarısız oluyor). **Durum:** Düzeltildi (iyilestirme dalı).

### H-005 · Kayıt dosyasından okunan değer dosya yolunu belirliyor
- **Bulan:** SonarQube · **Önem:** engelleyici (pratikte düşük risk) · **Tür:** CWE-22 yol aşımı (K5)
- **Yer:** `araclar/sesli/okuma.py` _json_yaz(). **İnceleme:** SonarQube'un gösterdiği yerde yol içerikten gelmiyor (yanlış
  alarm); ama aynı türün gerçek örneği yeni deneme deposundaydı: dosya adı JSON'dan okunup siliniyordu.
- **Düzeltme:** Deneme dosya adı yalnız `<özet>.deneme-N.wav` biçiminde kabul edilir; plan dosyası yapı denetiminden geçer,
  bozuksa program düşmez. **Tür denetimi:** iki test (eski kodda başarısız). **Durum:** Düzeltildi (iyilestirme dalı).

### H-006 · Önbellek adlarında MD5/SHA1 güvenlik amaçlı mı belirtilmemiş
- **Bulan:** bandit (yüksek), SonarQube (kritik) · **Tür:** A04 · **Durum:** Düzeltildi (`usedforsecurity=False`; önbellek
  adları değişmedi, doğrulandı).

### H-007 · torch 2.6.0'da 25 bilinen güvenlik açığı
- **Bulan:** pip-audit · **Tür:** A03 Tedarik zinciri (G4)
- **Düzeltme:** torch 2.13.0 (bilinen açığı olmayan ilk sürüm, OSV ile doğrulandı). torchaudio 2.9+ WAV okuma/yazma için
  TorchCodec + sistem FFmpeg istiyordu: WAV işleri soundfile'a taşındı (torchaudio 2.6 da arka planda soundfile
  kullanıyordu; gerçek bloklarla bayt bayt aynı). Ses verisi, örnekleme dönüşümü ve MP3 iki sürümde bayt bayt aynı;
  SQUIM kalite puanı 6. ondalıkta farklı (kayıt 2 ondalık). **Durum:** Düzeltildi (iyilestirme dalı); `.venv-ses`
  6. adımda kodla birlikte güncellenecek.

### H-008 · Yayın aracında rollup açığı
- **Bulan:** npm audit · **Tür:** A03
- **Kök neden:** netlify-cli 23 (4 ana sürüm geride) kendi içinde eski rollup taşıyordu; dışarıdan sabitlenemedi.
- **Düzeltme:** netlify-cli 27.16.1. Sitenin çalışma zamanı paketlerinde açık: 0. Geliştirme araçlarında (Lighthouse CI,
  Stryker, netlify-cli alt paketleri) 35 açık kaldı, 0 kritik; siteye ve okumaya girmez, npm'in önerdiği "düzeltme"
  araçların eski sürümlerine dönmek. **Durum:** Düzeltildi (çalışma zamanı); geliştirme araçları izleniyor.

### H-009 · Ana sayfada 20 yerde yetersiz renk kontrastı
- **Bulan:** axe, Lighthouse · **Tür:** Erişilebilirlik (O1) · **Durum:** Açık.

### H-010 · Testler koda sokulan hataların yalnız %57'sini yakalıyor
- **Bulan:** mutmut (mutasyon testi) · **Tür:** Zayıf test · **Tür denetimi:** Mutasyon puanı her gönderimde ölçülür.
- **Durum:** Açık. Hedef %80.

### H-011 · Kendi koduma 90+ puan verdim, gerçek 64
- **Bulan:** Bağımsız ölçüm · **Tür:** Süreç (S3)
- **Kök neden:** Testleri ve puanı kodu yazan verdi; "testler geçiyor", "kod sağlam" diye sunuldu.
- **Tür denetimi:** Puanlama sistemi (formül ölçümden önce yazıldı); kod yazan puan vermez.
- **Durum:** Kapandı (süreç değişti).

### H-012 · Scorecard eklentisi Mac makinede çalışmıyor, GitHub ölçümü düştü
- **Bulan:** GitHub Actions (ilk çalıştırma) · **Tür:** Hedef ortam uyumu (S2)
- **Kök neden:** Eklentinin yalnız Linux'ta çalıştığı kontrol edilmedi.
- **Tür denetimi:** Kontrol listesi S2; bir ölçümün düşmesi artık öbürlerini durdurmuyor.
- **Durum:** Düzeltildi (Scorecard ayrı Linux işinde).

### H-013 · Bölünemeyen blok "bölünecek" diye kalıcı işaretleniyordu
- **Bulan:** Mevcut test (test_isci_cli), birleştirmeden önce · **Önem:** orta · **Tür:** Kalıcı durum (K3)
- **Kök neden:** Boş yanıtta blok, bölünüp bölünemeyeceğine bakılmadan diske "bölünecek" diye işaretleniyordu. Tek
  paragraflık blokta bu, geçici bir boş yanıttan sonra bloğun bir daha hiç denenmemesi demekti.
- **Tür denetimi:** test_tek_paragraflik_blok_bos_yanitta_kalici_isaretlenmez.
- **Durum:** Düzeltildi (iyilestirme dalı).

### H-014 · Testler çalıştıkları makinenin saat dilimine bağlıydı
- **Bulan:** GitHub Actions (ilk tam ölçüm) · **Önem:** orta · **Tür:** Hedef ortam uyumu (S2)
- **Kök neden:** "Kota TR 11:05'te yenilenir" beklentisi Türkiye saatine göre yazılmıştı; GitHub makinesi UTC.
  Kod doğruydu, testler makineye göre geçip kalıyordu. Testler kalınca mutasyon testi de hiç başlamadı.
- **Düzeltme:** Test paketi her makinede Türkiye saatiyle çalışır (`testler/__init__.py`). UTC'de yeniden üretildi,
  düzeltmeden sonra UTC'de 127 test geçti. **Tür denetimi:** GitHub ölçümü her gönderimde UTC'de çalışır.
- **Durum:** Düzeltildi (iyilestirme dalı).

### H-015 · Veri katmanı Gemini modülünü çağırıyordu (katman ihlali)
- **Bulan:** import-linter (otomatik ölçüm), kendi yarım kodumda · **Tür:** Mimari
- **Kök neden:** İstek defteri özeti kota gününü `gemini` modülünden alıyordu; veri katmanı üst katmanı çağıramaz.
- **Düzeltme:** Kota takvimi en alt katmanda kendi modülünde (`sesli/kota.py`). **Durum:** Düzeltildi (iyilestirme dalı).
