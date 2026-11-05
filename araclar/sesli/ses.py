"""Ses dizileri: WAV okuma/yazma, örnekleme hızı dönüşümü, MP3 kodlama, Whisper dökümü ve konuşma kalitesi ölçümü.

Ağır kütüphaneler (torch, torchaudio, mlx_whisper) ilk kullanımda yüklenir: zamanlayıcı ve testler onlarsız çalışır.
Bütün sesler 24 kHz, tek kanal, [-1, 1] aralığında float32 dizilerdir.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, TypeAlias

import numpy as np
import numpy.typing as npt

Dalga: TypeAlias = npt.NDArray[np.float32]
"""Ses dizisi: tek kanal, [-1, 1] aralığında float32."""

SR = 24000
WHISPER = "mlx-community/whisper-large-v3-turbo"
# SQUIM PESQ tahmini: temiz 3.8 blokları 3,2-3,8; bozulan 2.5 blokları sonda 1,3-2,0 (29 Ekim ölçümü)
KALITE_SINIR = 2.6
KALITE_DUSUS = 1.0  # bloğun başı ile sonu arası bu kadar düşerse ses giderek bozuluyor demektir


def sessizlik(sn: float) -> Dalga:
    return np.zeros(int(SR * sn), dtype=np.float32)


def wav_oku(yol: Path) -> Dalga:
    import torchaudio as ta
    return np.asarray(ta.load(str(yol))[0][0].numpy(), dtype=np.float32)


def wav_yaz(yol: Path, ses: Dalga) -> None:
    """16 bit PCM; önce geçici dosyaya yazılıp yerine taşınır, yarım dosya önbelleğe girmez."""
    import torch
    import torchaudio as ta
    gecici = yol.with_name(yol.stem + ".yaziliyor.wav")
    ta.save(str(gecici), torch.from_numpy(ses).unsqueeze(0), SR, encoding="PCM_S", bits_per_sample=16)
    gecici.replace(yol)


def yeniden_ornekle(ses: Dalga, kaynak_hz: int, hedef_hz: int) -> Dalga:
    if kaynak_hz == hedef_hz:
        return ses
    import torch
    import torchaudio as ta
    return np.asarray(ta.functional.resample(torch.from_numpy(ses), kaynak_hz, hedef_hz).numpy(), dtype=np.float32)


def kirp(ses: Dalga) -> Dalga:
    """Baştaki ve sondaki sessizliği atar (kısa pay bırakarak)."""
    dolu = np.flatnonzero(np.abs(ses) > 0.02)
    return ses[max(0, dolu[0] - int(SR * 0.05)):dolu[-1] + int(SR * 0.1)] if len(dolu) else ses


def mp3_yaz(yol: Path, ses: Dalga, kbps: int = 128) -> None:
    import lameenc
    ses = ses / max(1e-6, float(np.abs(ses).max())) * 0.89
    enc = lameenc.Encoder()
    enc.set_bit_rate(kbps)
    enc.set_in_sample_rate(SR)
    enc.set_channels(1)
    enc.set_quality(2)
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_name(yol.name + ".yaziliyor")
    gecici.write_bytes(enc.encode((ses * 32767).astype(np.int16).tobytes()) + enc.flush())
    gecici.replace(yol)


# --- Whisper ---

def dok(ses: Dalga, sr: int = SR, onceki_metne_bagli: bool = False) -> str:
    import mlx_whisper
    w = yeniden_ornekle(ses, sr, 16000)
    sonuc = mlx_whisper.transcribe(w, path_or_hf_repo=WHISPER, language="tr",
                                   condition_on_previous_text=onceki_metne_bagli)
    return str(sonuc["text"]).strip()


def kelime_zamanlari(ses: Dalga) -> list[tuple[str, float, float]]:
    """[(sade kelime, başlangıç sn, bitiş sn)]."""
    import mlx_whisper
    from .karsilastir import duyulani_arit, sade_kelimeler
    w = yeniden_ornekle(ses, SR, 16000)
    sonuc = mlx_whisper.transcribe(w, path_or_hf_repo=WHISPER, language="tr", condition_on_previous_text=False,
                                   word_timestamps=True)
    return [(x, float(k["start"]), float(k["end"])) for seg in sonuc["segments"] for k in seg.get("words", [])
            for x in sade_kelimeler(duyulani_arit(k["word"]))]


# --- konuşma kalitesi ---

@lru_cache(maxsize=1)
def _squim() -> Any:
    from torchaudio.pipelines import SQUIM_OBJECTIVE
    return SQUIM_OBJECTIVE.get_model().eval()


def kalite(ses: Dalga) -> tuple[float, float]:
    """Referanssız konuşma kalitesi (torchaudio SQUIM, PESQ tahmini): her 30 sn'den 5 sn'lik örnek; (baş, son)
    ortalamaları. Kelimeler doğru olduğu hâlde giderek bozulan sesi (2.5 Flash, Raşomon) Whisper göremiyor, bu görüyor."""
    import torch
    x = torch.from_numpy(yeniden_ornekle(ses, SR, 16000))
    puan = []
    for b in range(0, max(1, len(x) - 16000 * 5), 16000 * 30):
        with torch.no_grad():
            puan.append(float(_squim()(x[b:b + 16000 * 5].unsqueeze(0))[1]))
    u = max(1, len(puan) // 3)
    return sum(puan[:u]) / u, sum(puan[-u:]) / u


def kalite_bozuk(bas: float, son: float) -> bool:
    return son < KALITE_SINIR or bas - son > KALITE_DUSUS
