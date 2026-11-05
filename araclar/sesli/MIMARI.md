# Sesli kitap üretim sistemi: mimari

Çevrilmiş ya da derlenmiş tam metinleri Gemini TTS ile okutur, her bloğu Whisper ve ses kalitesi ölçümüyle denetler,
geçenleri teslim klasörüne koyar ve "Melih'ten Dinle" sitesinin yayın klasörünü hazırlar.

```
podcast/eserler.json ─► hazirlik ─► fola/seslendirme-metni.txt
                                         │
                 zamanlayici (uzun ömürlü süreç, kota ve atama)
                                         │  her eser ayrı alt süreçte
                                         ▼
                 isci ─► okuma ─► gemini (TTS)      ─► .tmp/gemini-parcalar/<özet>.wav
                           │  └─► yama  (eksik cümle onarımı)
                           └─► kontrol (Whisper) ─► fola/kontrol.json
                                         │
                 zamanlayici ─► teslim ─► ~/Desktop/sesli kitap fola/<araç>/NN - Eser - Yazar.mp3
                                                   │
                                          site ─► ~/Library/Caches/melihten-dinle/yayin  (deploy elle, onayla)
```

## Katmanlar

| Katman | Modüller | Kural |
|---|---|---|
| Veri ve ayar | `yollar`, `ayar`, `katalog`, `durum`, `olcum` | Bütün yollar `Yollar`'da; eser bilgisi yalnız `podcast/eserler.json`'da |
| Saf kurallar | `metin`, `karsilastir`, `ceviri` | Dosya, ağ ya da model kullanmaz; birim testleri hızlı |
| Dış dünya | `gemini`, `ses` | Ağır kütüphaneler (torch, mlx_whisper, google-genai) ilk kullanımda yüklenir |
| İş akışı | `hazirlik`, `okuma`, `yama`, `kontrol`, `teslim`, `site` | Bağımlılıklar parametreyle verilir (testte sahtesi) |
| Süreç | `zamanlayici`, `isci`, `cli` | Çıkış kodları `isci.Cikis`; dış bağımlılıklar `zamanlayici.Bagimliliklar` |

Bağımlılık yalnız aşağı doğrudur: saf kurallar hiçbir iş akışı modülünü içe aktarmaz; hiçbir modül başka bir
betiğin dosyasını ayrıştırmaz.

## Değişmezler (bozulursa kota boşa gider ya da yanlış teslim olur)

1. **Blok önbellek adı** `md5(metin|model|ses|üslup)[:12].wav`. `metin.sabit_bloklar`, `metin.paragraflar`,
   `metin.sonraki_sinir` ve `gemini.USLUP` bir harf değişirse okunmuş bloklar tanınmaz. `testler/uyumluluk.py`
   gerçek eserlerle bunu denetler: her değişiklikten sonra çalıştırın.
2. **Bir eser tek sesle okunur.** Atanan araç eseri bitirir; `ortak` araçlar aynı sesle (Fola) sürdürebilir.
3. **Teslim koşulu**: harf düzeyinde eşleşme ≥ %97, 0,90 altı blok yok, atlama yok, ses kalitesi bozulmamış.
4. **Durum dosyası** (`.tmp/fola-atama.json`) yalnız `DurumDeposu.degistir()` ile yazılır: kilit + en güncel hâli
   okuma + atomik yazma. Program çalışırken elle düzenlemek güvenlidir.
5. **Silme yok**: eskiyen teslim kopyaları Çöp Sepeti'ne taşınır.

## Hata modeli

| Durum | Nerede | Sonuç |
|---|---|---|
| Günlük kota doldu | `gemini.KotaDoldu` → `Cikis.KOTA` | Araç bugün durur, eser yarın aynı araçla sürer |
| Güvenlik reddi, kısa metin | `GuvenlikReddi` → `Cikis.GUVENLIK` | Eser bu araçtan alınır (`ret`) |
| Güvenlik reddi ya da boş yanıt, uzun blok | `okuma.Okuyucu._bolerek` | Blok ikiye bölünüp yeniden denenir |
| Asılı istek (Mac uyudu) | `gemini._sureli` | Duvar saatiyle 15 dk sonra kesilir, istemci yenilenir |
| Bağlantı/sunucu sorunu sürdü | `GeciciHata` → `Cikis.GECICI` | 10 dk beklenir; eser araçtan alınmaz |
| Beklenmeyen hata | `Cikis.HATA` | 2. kezde eser araçtan alınır (kota döngüde yanmasın) |
| Kontrolden geçmedi | `zamanlayici._teslim` | Önce yalnız sorunlu bloklar yeniden okunur, sonra araçtan alınır |

## Komutlar

```sh
.venv-ses/bin/python araclar/sesli_kitap.py durum                 # ne nerede (hiçbir şeyi değiştirmez)
caffeinate -is .venv-ses/bin/python -u araclar/sesli_kitap.py oku >> .tmp/fola-sirayla.log 2>&1
.venv-ses/bin/python araclar/sesli_kitap.py ceviri london-martin-eden   # tr/NN.md → iki metin (ceviri.json)
.venv-ses/bin/python araclar/sesli_kitap.py kontrol london-beyaz-dis    # yeniden kontrol (Whisper önbellekten)
.venv-ses/bin/python araclar/sesli_kitap.py teslim
.venv-ses/bin/python araclar/sesli_kitap.py site --kuru                 # yayın klasörü (yazmadan önizleme)
```

`caffeinate -is` yalnız fişe takılıyken uykuyu engeller: pilde kapak kapanırsa Mac uyur, okuma durur
(istek askıda kalmaz, uyanınca sürer).

## Yeni eser eklemek

1. `podcast/eserler.json`'a kayıt (`durum: "etkin"`, çeviriyse `yalniz_fola: true`).
2. Çeviri ise `podcast/<ad>/tr/NN.md` bölümleri ve `podcast/<ad>/ceviri.json` (okunuşlar); `sesli_kitap.py ceviri <ad>`.
3. Zamanlayıcı yeniden başlatılmadan bir sonraki turda eseri kuyrukta görür.

## Testler

```sh
cd araclar && ../.venv-ses/bin/python -m unittest discover -s testler -t .      # birim (~30 sn; gerçek veri testi hariç)
cd araclar && ../.venv-ses/bin/python -m unittest testler.uyumluluk        # gerçek veriyle uyum (~3 dk)
cd araclar && ../.venv-ses/bin/python -m mypy                                  # sıkı tip denetimi (ayarı: araclar/mypy.ini)
cd kitaplik && npm test                                                         # şifre kapısı
cd kitaplik && npm run tip                                                      # site kodunun tip denetimi (Netlify'ın Deno'su)
```

Tip denetimi `strict` kipindedir: her işlevin parametre ve dönüş türü yazılıdır, `None` olabilecek değer
denetlenmeden kullanılamaz. Ses dizileri her yerde `ses.Dalga` (float32) türündedir. torch, whisper, google-genai
gibi büyük kütüphanelerin içi denetlenmez; onlarla konuşan yerler `Any` ile açıkça işaretlidir.

## Ortam notu: iCloud

Proje Masaüstü'nde, yani iCloud'da. "Mac depolamasını en iyi duruma getir" açık olduğu için iCloud uzun süre
açılmayan dosyaları (Python kütüphaneleri, eski metinler, teslim edilmiş MP3'ler) bilgisayardan kaldırıyor; ilk
okumada dosya başına saniyeler süren indirme oluyor. 5 Kasım 2026'da gerekli dosyalar `brctl download` ile geri
indirildi. Kalıcı çözüm `.venv-ses` ve `.cache`'i iCloud dışına almak ya da Finder'da "Her zaman bu Mac'te tut"
seçeneğini açmaktır (kullanıcı kararı).

## Eski betikler

`araclar/eski/` (Emel, Live, Vikikaynak dönemi ve yeni pakete taşınan betikler). Kullanılmaz; başvuru için durur.
