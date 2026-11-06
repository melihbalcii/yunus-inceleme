# Hata defteri

Bulunan her hata buraya yazılır. Amaç yalnız o hatayı değil, **o hata türünü** bir daha yaşamamak. Her kayıtta şu
sorunun cevabı vardır: "Bu türden bir hata tekrar olursa onu otomatik olarak ne yakalayacak?"

**Kaçan hata sayısı**, yani bizden önce başkasının bulduğu hata, her ay ayrıca sayılır. Hedef, bu sayının düşmesi.

| Ay | Bizden önce başkasının bulduğu | Araçların bulduğu | Bizim bulduğumuz |
|---|---|---|---|
| Kasım 2026 | 1 (Yunus: H-001) | 12 (H-004…H-012, H-014, H-015, H-022) | 10 (H-002, H-003, H-013, H-016…H-021, H-023) |

## Kayıtlar

### H-001 · Gemini isteği hata durumunda arka planda 2–4 kez yaptırılıyor
- **Bulan:** Yunus (insan incelemesi), 5 Kasım 2026 · **Önem:** yüksek (kota kaybı)
- **Tür:** Dış çağrıda istisnai durum (OWASP A10:2025) · Kontrol listesi D2, D3, D4
- **Kök neden:** Süre dolunca istek iptal edilmeden bırakılıp yenisi atılıyordu. Üç katman (istek, blok, eser) ayrı
  ayrı yeniden deniyordu, denemeler çarpılıyordu.
- **Neden kaçtı:** Testleri kodu yazan yazdı ve yalnız "her şey yolunda" durumunu sınadı. Kanıt okuma günlüğünde
  vardı, bakılmadı.
- **Tür denetimi:** Hata senaryosu testleri (istek sayısını doğrular); rastgele hata sırası (Hypothesis + başvuru
  modeli, 400 senaryo); gerçek ağ arızası (Toxiproxy: ret, kopma, askı, yarım yanıt, gecikme — sunucuya ulaşan istek
  sayılır); çökme testi (süreç öldürme); canlı alarm (bir kota gününde 4 istek boşa giderse okuma durur).
- **Durum:** Düzeltildi; 6 Kasım'da gerçek projeye aktarıldı, okuma yeni kodla sürüyor.

### H-002 · Kota bitince okunmuş ses kayboluyor
- **Bulan:** Okuma günlüğü (geriye dönük tarama), 5 Kasım 2026 · **Önem:** yüksek
- **Tür:** Yarıda kalma (K2, K3)
- **Kök neden:** Bir bloğun denemeleri diske yazılmadan bellekte tutuluyordu.
- **Gerçek zarar (araclar/haftalik_denetim.py ile bütün günlük tarandı):** 4 olay, 7 istek, ~85 dk ses kayboldu
  (26.10 Toprak 2 deneme, 26.10 Usher 2 deneme, 01.11 İdam Mahkûmu 1 deneme, 02.11 Dilin Âfetleri 2 deneme).
  Elle yalnız biri bulunmuştu.
- **Tür denetimi:** Deneme deposu ve testi; kayıt denetimi (haftalik_denetim.py "kaybolmuş olabilecek okuma");
  planlı: çökme testi.
- **Durum:** Düzeltildi; çökme testiyle kanıtlandı (H-018 kalan parçasıydı), 6 Kasım'da gerçek projede.

### H-003 · Okuma programı iki kez başlatılabiliyor
- **Bulan:** Biz (H-001 incelemesi sırasında) · **Önem:** orta · **Tür:** Aynı anda çalışma (E1)
- **Tür denetimi:** Tek kopya kilidi testi. **Durum:** Düzeltildi; 6 Kasım'da gerçek projede (ilk gece kilit doğru çalıştı).

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
  SQUIM kalite puanı 6. ondalıkta farklı (kayıt 2 ondalık). Uçtan uca: Beyaz Diş (374,8 dk) torch 2.13 ile istek
  atmadan baştan üretildi; MP3, kalite kaydı ve plan torch 2.6 çıktısıyla (o da teslim edilenle) bayt bayt aynı,
  metin kontrolü %99,5. **Durum:** Düzeltildi; `.venv-ses`
  6. adımda kodla birlikte güncellenecek.

### H-008 · Yayın aracında rollup açığı
- **Bulan:** npm audit · **Tür:** A03
- **Kök neden:** netlify-cli 23 (4 ana sürüm geride) kendi içinde eski rollup taşıyordu; dışarıdan sabitlenemedi.
- **Düzeltme:** netlify-cli 27.16.1. Sitenin çalışma zamanı paketlerinde açık: 0. Geliştirme araçlarında (Lighthouse CI,
  Stryker, netlify-cli alt paketleri) 35 açık kaldı, 0 kritik; siteye ve okumaya girmez, npm'in önerdiği "düzeltme"
  araçların eski sürümlerine dönmek. **Durum:** Düzeltildi (çalışma zamanı); geliştirme araçları izleniyor.

### H-009 · Ana sayfada yetersiz renk kontrastı
- **Bulan:** axe, Lighthouse · **Tür:** Erişilebilirlik (O1)
- **İnceleme:** İlk ölçümdeki 20 bulgu, sitenin eser listesi olmadan (boş sayfa) ölçülmesindendi. Gerçek sayfa ölçülünce
  (örnek eser listesiyle) 4 gerçek bulgu kaldı: ikincil gri yazı (`--soluk-2` #6f6f6f) koyu zeminde 3,72 oranındaydı.
- **Düzeltme:** #878787 (#121212 üstünde 5,2; #1c1c1c üstünde 4,75; eşik 4,5). axe: 0 bulgu. **Durum:** Düzeltildi
  (siteye yayın kullanıcı onayıyla).

### H-010 · Testler koda sokulan hataların yalnız %57'sini yakalıyor
- **Bulan:** mutmut (mutasyon testi) · **Tür:** Zayıf test · **Tür denetimi:** Mutasyon puanı her gönderimde ölçülür.
- **Durum:** Mutasyon puanı %57,1 → %89,0 (6 Kasım; kalan kaçakların 126'sı eşdeğer, onlar hariç ~%91). Hedef %90.

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

### H-016 · Okuma ortamının kütüphaneleri yalnız iCloud'da, program açılışta takılıyor
- **Bulan:** Biz (rastgele senaryo testi yazarken, 6 Kasım 2026) · **Önem:** yüksek (okuma hiç başlayamaz)
- **Tür:** Hedef ortam uyumu (S2), dış bağımlılık
- **Kök neden:** Proje Masaüstü'nde, Masaüstü iCloud'a eşitleniyor; macOS yer açmak için `.venv-ses` içindeki torch
  kütüphanelerini (ör. 186 MB libtorch_cpu) Mac'ten kaldırıp yalnız iCloud'da bırakmış. Yeniden başlatmadan sonra
  iCloud indirmesi ilerlemedi: torch'u yükleyen her komut (okuma, test) uyarı vermeden sonsuza kadar bekledi.
  Aynı durumda 113.925 dosya / 19,1 GB (teslim MP3'leri, `.cache/huggingface` modeli) var.
- **Tür denetimi:** `haftalik_denetim.py` artık okuma ortamında (`.venv-ses`, `.cache/python`, `.cache/huggingface`,
  `araclar`) yalnız iCloud'da duran dosya var mı bakıyor, varsa alarm veriyor (`test_haftalik_denetim`, 3 test). İlk
  çalıştırmada benim elle çıkardığım listede olmayan `.cache/python`'u (Python'un kendisi) yakaladı.
- **Çözüm:** Finder'da klasöre sağ tıkla → "İndirileni Tut". Kullanıcı 6 Kasım'da üçünü işaretledi; `.cache/python`
  eklenecek.
- **Durum:** Düzeltildi; 6 Kasım'da okuma ortamı tamamen Mac'te, denetim her oturumda kontrol ediyor.

### H-017 · İstek sırasında çöken program blok başına günlük tavanı aşabiliyordu
- **Bulan:** Çökme testi (`testler/test_cokme.py`), 6 Kasım 2026 · **Önem:** yüksek (kota kaybı) · **Tür:** Yarıda kalma (K2)
- **Kök neden:** Blok sayacı istek BİTTİKTEN sonra diske yazılıyordu. İstek sürerken süreç ölürse (elektrik, kill -9,
  yeniden başlatma) sayaç hiç artmıyordu: üst üste 7 çökmede 7 istek gitti, tavan 4.
- **Düzeltme:** Bütçe istekten ÖNCE harcanmış sayılıp yazılır, harcanmayan kısmı sonra iade edilir. Çökmede sayaç
  fazla sayar (güvenli yön). **Tür denetimi:** gerçek süreç öldürülerek yapılan çökme testi. **Durum:** Düzeltildi.

### H-018 · Gelen ses ölçülürken program çökerse ses kayboluyordu
- **Bulan:** Çökme testi, 6 Kasım 2026 · **Önem:** yüksek (H-002'nin kalan parçası) · **Tür:** Yarıda kalma (K2, K3)
- **Kök neden:** Gemini'den gelen ses önce Whisper ile ölçülüyor (dakikalar), ancak sonra diske yazılıyordu. Bu arada
  çökme olursa ses kayboluyor, kota boşa gidiyor, ertesi açılışta aynı blok yeniden isteniyordu.
- **Düzeltme:** Ses gelir gelmez "bekleyen" olarak diske yazılır; açılışta önce bekleyenler ölçülür, yeni istek atılmaz.
- **Tür denetimi:** çökme testi (ölçüm anında öldürme). **Durum:** Düzeltildi.

### H-019 · Mutasyon ölçümü 208 yakalanan mutasyonu "yakalanmadı" sayıyordu
- **Bulan:** Biz (mutasyon sonuçlarını modül modül incelerken), 6 Kasım 2026 · **Tür:** Ölçüm hatası (S2)
- **Kök neden:** mutmut her mutasyonu çatallanmış (fork) süreçte sınar. macOS'ta çatallanmış süreç, ağ kütüphanesi
  (httpx/urllib) sistemin vekil sunucu ayarını sorguladığında çöküyor (segfault). Ağ kullanan testler bu yüzden
  başarısız olmak yerine çöktü; mutmut çökmeyi "yakalandı" saymıyor. `gemini.py`'nin puanı %46 görünüyordu.
- **Düzeltme:** Ölçümde `NO_PROXY='*'`: vekil sorgusu yapılmaz. Tek tek doğrulandı: çöken mutasyonlar testlerce yakalanıyor.
- **Ayrıca:** Ağ testi, öldürülünce Toxiproxy sürecini açık bırakıyordu (bir ölçümde 207 süreç). Toxiproxy artık bekçi
  kabukla başlıyor; `kill -9` sonrası da kapandığı doğrulandı. **Durum:** Düzeltildi.

### H-020 · Kayıt denetiminin iki yanlış alarmı (ilk canlı gece)
- **Bulan:** Biz (6 Kasım gecesi okumanın denetimini incelerken) · **Tür:** Ölçüm/denetim hatası
- **1) "İki okuma programı kopyası":** Mac'i uyutmayan `caffeinate` sarmalayıcısının komut satırında da "sesli_kitap.py oku"
  geçiyordu; kopya sayıldı. Artık sayılmıyor (test: `SurecVeTekrarTesti`).
- **2) "Aynı metin birden çok kez seslendirildi":** Bulunan 4 metnin hepsi tasarım gereği yeniden okumaydı (atlama ya da
  "ses bozuluyor" yüzünden 2-3 deneme; günlükte görüldü). Artık 3 denemeye kadar bilgi olarak, fazlası alarm olarak yazılır.
- **3) Rapor üzerine yazılıyordu:** gün içinde ikinci denetim ilkinin bulgularını siliyordu; artık eklenir.
- **Canlı doğrulama (aynı gece):** Gemini 503 "yoğunluk" yanıtlarında (1-2 sn'de dönen ret) kod en çok 2 deneyip 10 dk
  bekledi; blok başına günlük tavan (4) dolunca 03:26'da 5. isteği hiç atmadı; Flash'ı dinlenmeye aldı; yeni kodla
  başlayınca canlı alarm (bugün 5 boşa istek ≥ 4) okumayı kota yenilenene dek durdurdu. **Durum:** Düzeltildi.

### H-021 · Sık gönderimde GitHub ölçümü hiç bitemiyordu
- **Bulan:** Biz (6 Kasım gecesi, 5 saat boyunca tek ölçüm sonuçlanmadı) · **Tür:** Ölçüm düzeni (S2)
- **Kök neden:** İş akışında `cancel-in-progress: true`: her yeni gönderim çalışan ölçümü iptal ediyordu. Ölçüm ~1 saat
  sürdüğü için sık gönderimde hiçbiri tamamlanmadı. Ayrıca takılan bir ölçüm 5 saatlik sınıra kadar sırayı kilitledi.
- **Düzeltme:** `cancel-in-progress: false` (çalışan biter, sırada yalnız en son gönderim bekler); süre sınırı 3 saat.
- **Durum:** Düzeltildi.

### H-022 · Model ailesi tutarsız ayrılıyordu (3.8 Flash ile 3.1 aynı aile sayılıyordu)
- **Bulan:** Mutasyon testi (zamanlayici._aile kaçakları incelenirken), 6 Kasım 2026 · **Önem:** orta (gizli)
- **Kök neden:** Aile, model adının sondan bölünmesiyle bulunuyordu: 3.8 Lite → "gemini-3.8" ama 3.8 Flash ve 3.1 →
  "gemini". 3.8 için kodda özel bir istisna vardı; 3.1 "kesik" ölçüm kaydetseydi 3.8 Flash'ın blok boyu sessizce küçülürdü.
- **Düzeltme:** Aile sürüm numarasıdır (gemini-3.8, gemini-3.1, gemini-2.5); istisna kaldırıldı. Gerçek ölçüm dosyasıyla
  sonuçlar değişmedi (3.8: 1134 sn, 2.5: 470, 3.1: 570). **Tür denetimi:** AileTesti. **Durum:** Düzeltildi.

### H-023 · Kayıt denetimi yeni koddaki bir yeniden deneme iletisini tanımıyordu
- **Bulan:** Biz (kalan ileti kaçaklarını incelerken), 6 Kasım 2026 · **Tür:** Ölçüm/denetim uyumu
- **Kök neden:** Denetim, eski kodun "bağlantı koptu ya da zaman aşımı" iletisini arıyordu; yeni kod bağlanamayınca
  "bağlanılamadı (kota harcanmadı), tekrar" yazıyor. Bu yeniden denemeler sayılmıyordu.
- **Düzeltme:** Sözcük listesine eklendi. **Tür denetimi:** IletiSozlesmesiTesti, okuma programının gerçek iletilerini
  denetimin sözcükleriyle karşılaştırır (yeniden deneme, kesinti, yarım deneme). **Durum:** Düzeltildi.
