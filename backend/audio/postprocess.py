"""معالجة الصوت النهائية بجودة بث/إعلان احترافية.

السلسلة (بالترتيب):
    1) تشذيب السكوت الزايد
    2) High-pass  → شيل الزمزمة/الدبدبة (< 80Hz)
    3) De-esser   → تقليل حروف السين/الشين الحادّة (5–9kHz)
    4) EBU R128   → تطبيع الجهارة لـ ~ -14 LUFS (معيار البث/يوتيوب/سبوتيفاي)
    5) True-peak  → تأمين الذروة عند -1 dBTP (منع التشويش)
    6) Fade in/out
    7) (اختياري) Resample لـ 48kHz للإنتاج النهائي

كله محلي بالكامل (numpy + scipy + pyloudnorm) — من غير أي برنامج خارجي.
"""
from __future__ import annotations

import math

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.ndimage import uniform_filter1d
from scipy.signal import butter, resample_poly, sosfilt

# ── 1) تنضيف ──────────────────────────────────────────────────────────────


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


# ── 2) High-pass ──────────────────────────────────────────────────────────


def highpass(data: np.ndarray, sr: int, cutoff_hz: float = 80.0, order: int = 4) -> np.ndarray:
    """شيل الترددات الواطية (زمزمة/دبدبة/تنفّس) للصوت يبقى أنضف."""
    nyq = sr / 2.0
    if cutoff_hz <= 0 or cutoff_hz >= nyq:
        return data
    sos = butter(order, cutoff_hz / nyq, btype="highpass", output="sos")
    return sosfilt(sos, data, axis=0)


# ── 3) De-esser ───────────────────────────────────────────────────────────


def deess(
    data: np.ndarray,
    sr: int,
    *,
    low_hz: float = 5000.0,
    high_hz: float = 9000.0,
    threshold_db: float = -30.0,
    ratio: float = 4.0,
    max_reduction_db: float = 12.0,
    window_ms: float = 5.0,
) -> np.ndarray:
    """يقلّل حروف السين/الشين الحادّة (split-band de-esser).

    بيفصل نطاق الصفير (5–9kHz)، بيقيس غلافه، وبيقلّل مكسبه لما يعدّي العتبة.
    """
    nyq = sr / 2.0
    high_hz = min(high_hz, nyq * 0.95)
    if low_hz >= high_hz:
        return data

    sos = butter(2, [low_hz / nyq, high_hz / nyq], btype="band", output="sos")
    sibilance = sosfilt(sos, data, axis=0)

    rect = np.abs(sibilance)
    win = max(int(sr * window_ms / 1000.0), 1)
    power = uniform_filter1d(rect**2, win, axis=0)
    env = np.sqrt(np.maximum(power, 0.0))
    env_db = 20.0 * np.log10(env + 1e-12)

    over = np.maximum(env_db - threshold_db, 0.0)
    gain_db = np.clip(-over * (1.0 - 1.0 / ratio), -max_reduction_db, 0.0)
    gain = 10.0 ** (gain_db / 20.0)

    # نشيل الصفير الأصلي ونرجّعه بالمكسب المخفّض
    return data - sibilance * (1.0 - gain)


# ── 4) EBU R128 loudness ──────────────────────────────────────────────────


def measure_loudness(data: np.ndarray, sr: int) -> float:
    """يقيس الجهارة المتكاملة (LUFS). بيرجّع -inf للصوت الساكت."""
    try:
        meter = pyln.Meter(sr)
        loud = meter.integrated_loudness(np.asarray(data, dtype=np.float64))
    except Exception:  # noqa: BLE001
        return float("-inf")
    return float(loud)


def normalize_loudness(data: np.ndarray, sr: int, target_lufs: float = -14.0) -> np.ndarray:
    """يوصل الجهارة للهدف (EBU R128)."""
    loud = measure_loudness(data, sr)
    if not math.isfinite(loud):
        return data
    return data * (10.0 ** ((target_lufs - loud) / 20.0))


# ── 5) True-peak safety ───────────────────────────────────────────────────


def peak_safety(data: np.ndarray, ceiling_db: float = -1.0) -> np.ndarray:
    """يضمن إن الذروة مش بتعدّي السقف (من غير تشويه)."""
    ceiling = 10.0 ** (ceiling_db / 20.0)
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    if peak > ceiling > 0:
        data = data * (ceiling / peak)
    return data


# ── 6) Fade ───────────────────────────────────────────────────────────────


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


# ── 7) Resample ───────────────────────────────────────────────────────────


def resample_audio(data: np.ndarray, sr_in: int, sr_out: int) -> tuple[np.ndarray, int]:
    """إعادة تنميط (مثلاً 24kHz للموديل → 48kHz للإنتاج)."""
    if sr_in == sr_out or sr_out <= 0:
        return data, sr_in
    g = math.gcd(int(sr_in), int(sr_out))
    up, down = sr_out // g, sr_in // g
    return resample_poly(data, up, down, axis=0), sr_out


# ── السلسلة الكاملة ────────────────────────────────────────────────────────


def postprocess(
    in_path: str,
    out_path: str | None = None,
    *,
    trim: bool = True,
    highpass_hz: float = 80.0,
    deesser: bool = True,
    target_lufs: float = -14.0,
    true_peak_db: float = -1.0,
    fade_ms: int = 10,
    target_sr: int | None = None,
) -> str:
    """يشغّل سلسلة المعالجة الاحترافية على ملف ويحفظ الناتج."""
    data, sr = sf.read(in_path, always_2d=False, dtype="float64")
    if data.size == 0:
        out_path = out_path or in_path
        sf.write(out_path, data, sr)
        return out_path

    if trim:
        data = trim_silence(data, sr)
    if highpass_hz:
        data = highpass(data, sr, highpass_hz)
    if deesser:
        data = deess(data, sr)
    if target_lufs is not None:
        data = normalize_loudness(data, sr, target_lufs)
    data = peak_safety(data, true_peak_db)
    data = apply_fade(data, sr, fade_ms)
    if target_sr:
        data, sr = resample_audio(data, sr, target_sr)

    data = np.clip(data, -1.0, 1.0)
    out_path = out_path or in_path
    sf.write(out_path, data, sr)
    return out_path


def analyze(path: str) -> dict[str, float]:
    """تقرير سريع: المدة + الجهارة + الذروة."""
    data, sr = sf.read(path, always_2d=False, dtype="float64")
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    return {
        "sr": float(sr),
        "seconds": len(data) / sr if sr else 0.0,
        "lufs": measure_loudness(data, sr),
        "peak_dbfs": 20.0 * math.log10(peak) if peak > 0 else float("-inf"),
    }
