# Melih'ten Dinle (arkadaşlarla paylaşılan sesli kitap sitesi)

`~/Desktop/sesli kitap/` klasöründeki tam eserleri şifreli bir sitede dinletir. Netlify, ücretsiz plan.
(Cloudflare denendi ve silindi: `pages.dev`, `workers.dev`, `r2.dev` Türkiye'den engelli. `netlify.app` açık.)

- Adres: https://melihten-dinle.netlify.app (Netlify hesabı haydanns@gmail.com, takım "melihbalciii")
- Ortak şifre: `.env` dosyasındaki `SIFRE` (git'e girmez). Büyük/küçük harf ve ı/i farkı sayılmaz.
  Netlify'daki ortam değişkenleri `SIFRE` ve `ANAHTAR` bununla aynı olmalı.
- Kaldığı yer, hız ve bitenler her dinleyicinin kendi tarayıcısında tutulur.

## Nasıl çalışır

- Şifre kapısı: `netlify/edge-functions/kapi.ts` her isteği (ses dahil) denetler; kuralları ve çerez biçimi
  `netlify/lib/oturum.ts`'de. `SIFRE` ya da `ANAHTAR` tanımlı değilse site hiç açılmaz (503).
  Testler: `npm test` (Node 24; Netlify'a dokunmaz). Tip denetimi: `npm run tip` (Netlify'ın indirdiği Deno ile).
- Ses: site kopyası **64 kbps** (Emel sesi kaynağında 48 kbps; 128 kbps ses katmıyor) ve Netlify 10 MB üstü
  dosyaları iyi sunmadığı için ~20 dakikalık parçalara bölünür. Oynatıcı parçaları tek kayıt gibi çalar.
  Teslim klasöründeki tek 128 kbps dosyaya dokunulmaz.
- Yayın klasörü Masaüstü dışında (iCloud'a gitmesin): `~/Library/Caches/melihten-dinle/yayin`

## Ücretsiz kota

Ücretsiz planda ayda 300 kredi; aktarım GB başına 20 kredi → ayda ~15 GB dinleme (64 kbps'de ~250 ortalama eser).
Kota dolarsa **ücret alınmaz**, takımdaki bütün siteler ay sonuna kadar durur (bist-portfoy-takip dahil).
Parça adresleri içerik özetli, tarayıcı bir yıl önbellekte tutar: aynı yeri yeniden dinlemek kotadan yemez.

## Yeni eser eklenince

```sh
.venv-ses/bin/python araclar/sesli_kitap.py site        # yalnız yeni/değişen eser kodlanır (--kuru: yazmadan önizleme)
cd kitaplik && set -a && . ./.env && set +a && npx netlify deploy --prod --dir ~/Library/Caches/melihten-dinle/yayin --site melihten-dinle
```

Netlify yalnız yeni/değişen dosyaları yükler. Katalogdan çıkan eser yayından da çıkar.

## Şifreyi değiştirmek

`.env` içinde `SIFRE`'yi değiştir, sonra Netlify'daki `SIFRE` ortam değişkenini aynı değere çek
(`npx netlify env:set SIFRE ...`) ve yeniden yayınla. Eski şifreyle açılmış oturumlar bir yıl geçerli kalır;
herkesi çıkarmak için `ANAHTAR`'ı da değiştir.

## Yerel deneme

```sh
cd kitaplik && npx netlify dev --dir ~/Library/Caches/melihten-dinle/yayin --port 8888 --offline
```
