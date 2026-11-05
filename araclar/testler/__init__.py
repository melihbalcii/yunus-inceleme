"""Testler her makinede Türkiye saatiyle çalışır (üretim ortamı bu Mac, Türkiye saati).

GitHub'ın makineleri UTC'dir: "kota TR 11:05'te yenilenir" gibi beklentiler orada şaşıyordu ve testler yalnız
makineye göre geçip kalıyordu (kalite/HATA-DEFTERI.md H-014). Saat dilimi bütün testlerden önce burada sabitlenir.
"""
import os
import time

os.environ["TZ"] = "Europe/Istanbul"
time.tzset()
