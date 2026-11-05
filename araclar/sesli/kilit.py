"""Tek kopya kilidi: aynı işi iki süreç aynı anda yapamaz.

Okuma programı yanlışlıkla iki kez başlatılırsa iki kopya aynı eseri aynı anda okur ve her bloğa iki kez kota
harcanır. Kilit `fcntl.flock` ile alınır: süreç ne biçimde biterse bitsin (çökme, kill -9 dahil) işletim sistemi kilidi
bırakır, eskimiş kilit dosyası sorun olmaz. Kilit dosyasında tutan sürecin numarası yazılıdır (yalnız bilgi için).
"""
from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator


class ZatenCalisiyor(Exception):
    def __init__(self, yol: Path, pid: str):
        super().__init__(f"başka bir süreç çalışıyor (süreç no {pid or '?'}; kilit: {yol})")
        self.pid = pid


@contextmanager
def tek_kopya(yol: Path) -> Iterator[None]:
    """Kilidi alır, blok bitince bırakır. Kilit başka süreçteyse beklemez: ZatenCalisiyor."""
    yol.parent.mkdir(parents=True, exist_ok=True)
    f = open(yol, "a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            f.seek(0)
            raise ZatenCalisiyor(yol, f.read().strip()) from None
        f.seek(0)
        f.truncate()
        f.write(str(os.getpid()))
        f.flush()
        yield
    finally:
        f.close()  # kilit dosyayla birlikte bırakılır
