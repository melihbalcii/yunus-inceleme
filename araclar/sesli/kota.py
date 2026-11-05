"""Gemini günlük ücretsiz kotasının takvimi: kota ABD Pasifik saatiyle gece yarısı yenilenir.

Yalnız tarih hesabıdır; hiçbir modüle bağlı değildir (en alt katman). Kota günü; istek defteri, bloğun günlük istek
bütçesi ve zamanlayıcının bekleme hesabında ortak kullanılır.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

KOTA_SAAT_DILIMI = ZoneInfo("America/Los_Angeles")


def kota_gunu(simdi: dt.datetime | None = None) -> str:
    """Günlük kotanın hangi güne ait olduğu (ABD Pasifik tarihi, "2026-11-05")."""
    return (simdi or dt.datetime.now().astimezone()).astimezone(KOTA_SAAT_DILIMI).date().isoformat()
