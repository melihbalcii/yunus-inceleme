# Kontrol listesi

Her değişiklik "bitti" denmeden önce bu liste baştan sona uygulanır. Kimse istemese de uygulanır. Bir madde
uygulanmazsa nedeni değişikliğin açıklamasına yazılır.

Maddeler kendi hayal gücümüzden değil, yıllarca birikmiş hata türlerinden gelir:
[OWASP Top 10:2025](https://owasp.org/Top10/2025/), [MITRE CWE Top 25](https://cwe.mitre.org/top25/),
[AWS Well-Architected güvenilirlik ilkeleri](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/welcome.html)
ve kendi [hata defterimiz](HATA-DEFTERI.md). "Otomatik" sütunu dolu olan madde, puanlama sisteminde her gönderimde
kendiliğinden denetlenir. Boş olanlar elle denetlenir ve otomatiğe çevrilmeyi bekler.

## 1. Dışarıya giden her çağrı (Gemini, ağ, alt süreç)
OWASP A10:2025 (istisnai durumlar), AWS güvenilirlik: zaman aşımı, yeniden deneme, idempotency.

| # | Soru | Otomatik |
|---|---|---|
| D1 | Yanıt hiç gelmezse ne olur? Süre sınırı duvar saatine mi bakıyor (Mac uyuyunca sayaç durur)? | test_hata_senaryolari |
| D2 | Yanıt geç gelirse aynı iş ikinci kez başlatılıyor mu? Aynı anda en çok kaç istek? | test_hata_senaryolari |
| D3 | "İstek hiç gitmedi" ile "gitti ama yanıt kayboldu" ayrı mı ele alınıyor? İkincisi kotayı yemiş olabilir. | test_hata_senaryolari |
| D4 | Yeniden deneme **tek bir katmanda** mı? Katmanlar ayrı ayrı denerse denemeler çarpılır. | — |
| D5 | Bir iş için harcanabilecek en çok istek (bütçe) yazılı ve sınanmış mı? | test_hata_senaryolari |
| D6 | Her istek bir deftere yazılıyor mu? Boşa giden istek ölçülebiliyor mu? | — |
| D7 | Bekleme süreleri üstel artıyor ve bir üst sınırı var mı? | — |

## 2. Kalıcı veri ve yarıda kalma
| # | Soru | Otomatik |
|---|---|---|
| K1 | Dosya yarım yazılabilir mi? (geçici dosyaya yaz → yerine taşı) | — |
| K2 | Program şu an çökse, yapılmış iş (okunmuş ses, harcanmış kota) kaybolur mu? | çökme testi (planlı) |
| K3 | Yeniden başlayınca kaldığı yerden mi sürüyor, baştan mı? Aynı iş tekrar yaptırılıyor mu? | test_hata_senaryolari |
| K4 | Elle yapılan düzenleme program tarafından ezilebilir mi? | test_katalog_durum |
| K5 | Okunan dosyadan gelen değer bir dosya yolunu belirliyor mu? (yol aşımı, CWE-22) | SonarQube |

## 3. Aynı anda çalışma
| # | Soru | Otomatik |
|---|---|---|
| E1 | Program iki kez başlatılırsa ne olur? Tek kopya kilidi var mı? | test_hata_senaryolari |
| E2 | Aynı dosyaya iki süreç aynı anda yazabilir mi? | test_katalog_durum |
| E3 | Arka planda bırakılan iş parçacığı hâlâ çalışıyor mu? | test_hata_senaryolari |

## 4. Güvenlik (OWASP Top 10:2025)
| # | Soru | Otomatik |
|---|---|---|
| G1 | Dışarıdan gelen değer (adres çubuğu, form, dosya) HTML'e kaçışsız yazılıyor mu? (A05 Injection, CWE-79 XSS) | SonarQube, CodeQL |
| G2 | Giriş ve oturum: şifre karşılaştırması sabit sürede mi, çerez imzalı mı, ayar eksikse kapı kapalı mı? (A07, A01) | node testleri |
| G3 | Gizli bilgi (anahtar, şifre) koda, günlüğe ya da ekrana yazılıyor mu? (A04) | — |
| G4 | Kullanılan kütüphanelerde bilinen açık var mı? Sürümler sabit mi? (A03 Tedarik zinciri) | pip-audit, npm audit |
| G5 | Hata mesajı içeriden bilgi sızdırıyor mu? (A02 Yanlış ayar) | — |
| G6 | Güvenlik olayları günlüğe yazılıyor ve fark ediliyor mu? (A09) | — |
| G7 | Herkese açık depoya kişisel veri (fotoğraf, telefon, ad) gidiyor mu? | — |

## 5. Ön yüz
| # | Soru | Otomatik |
|---|---|---|
| O1 | Renk kontrastı, ekran okuyucu etiketleri, klavyeyle kullanım | axe, Lighthouse |
| O2 | İnternet yokken ya da yavaşken site ne yapıyor? | — |
| O3 | Türkçe karakterler doğru sıralanıyor ve büyük harfe doğru çevriliyor mu? (i → İ) | SonarQube (kısmen) |

## 6. Sürecin kendisi
| # | Soru | Otomatik |
|---|---|---|
| S1 | Gerçek günlükler (okuma günlüğü, istek defteri) tarandı mı? Kanıt orada olabilir. | haftalik_denetim.py |
| S2 | Kullanılan araç ya da eklenti hedef ortamda çalışıyor mu? (Linux/Mac, sürüm) | — |
| S3 | Puanı kodu yazan vermedi, ölçüm verdi mi? | puanlama |
| S4 | Bulunan her hata hata defterine yazıldı ve **türünü** yakalayan denetim eklendi mi? | — |
