"""معالجة الصوت النهائية عشان الخرج يبقى بجودة إعلانية.

حالياً: تنضيف + تطبيع مستوى + تشذيب سكوت + fade.
TODO: EBU R128 (~-14 LUFS) عبر pyloudnorm/ffmpeg، و de-esser و EQ.
"""
from __future__ import annotations

import numpy as np
import soundfile as sf


def trim_silence(data: np.ndarray, sr: int, threshold_db: float = -45.0) -> np.ndarray:
    """يشيل السكوت الزايد من الأول والآخر."""
    if data.ndim > 1:
        mono = data.mean(axis=1)
    else:
        mono = data
    thresh = 10 ** (threshold_db / 20.0)
    loud = np.where(np.abs(mono) > thresh)[0]
    if loud.size == 0:
        return data
    start = max(int(loud[0]) - int(0.05 * sr), 0)
    end = min(int(loud[-1]) + int(0.10 * sr), len(data))
    return data[start:end]


def normalize_level(data: np.ndarray, target_dbfs: float = -1.0) -> np.ndarray:
    """تطبيع الذروة لمستوى مستهدف."""
    peak = np.max(np.abs(data)) if data.size else 0.0
    if peak == 0:
        return data
    target = 10 ** (target_dbfs / 20.0)
    return data * (target / peak)


def apply_fade(data: np.ndarray, sr: int, ms: int = 10) -> np.ndarray:
    n = max(int(sr * ms / 1000), 1)
    if len(data) <= 2 * n:
        return data
    ramp = np.linspace(0.0, 1.0, n, dtype=data.dtype)
    out = data.copy()
    if out.ndim > 1:
        out[:n] *= ramp[:, None]
        out[-n:] *= ramp[::-1][:, None]
    else:
        out[:n] *= ramp
        out[-n:] *= ramp[::-1]
    return out


def postprocess(
    in_path: str,
    out_path: str | None = None,
    *,
    trim: bool = True,
    target_dbfs: float = -1.0,
) -> str:
    """يشغّل سلسلة المعالجة على ملف ويحفظ الناتج."""
    data, sr = sf.read(in_path, always_2d=False)
    if trim:
        data = trim_silence(data, sr)
    data = normalize_level(data, target_dbfs)
    data = apply_fade(data, sr)
    out_path = out_path or in_path
    sf.write(out_path, data, sr)
    return out_path
