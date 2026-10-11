"""معالجة الصوت النهائية بجودة بث/إعلان احترافية.

السلسلة (بالترتيب):
    1) تشذيب السكوت الزايد
    2) High-pass  → شيل الزمزمة/الدبدبة (< 80Hz)
    3) De-esser   → تقليل حروف السين/الشين الحادّة (5–9kHz)
    4) Multiband  → ضغط/EQ متعدد النطاقات (اختياري: voice/warm/punch/broadcast)
    5) EBU R128   → تطبيع الجهارة لـ ~ -14 LUFS (معيار البث/يوتيوب/سبوتيفاي)
    6) Limiter    → تحديد القمم عند -1 dBTP (بدل تصغير المقطع بالكامل)
    7) Fade in/out
    8) (اختياري) Resample لـ 48kHz للإنتاج النهائي

كله محلي بالكامل (numpy + scipy + pyloudnorm) — من غير أي برنامج خارجي.
"""
from __future__ import annotations

import math

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.ndimage import maximum_filter1d, uniform_filter1d
from scipy.signal import butter, lfilter, lfilter_zi, resample_poly, sosfilt, sosfiltfilt

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


# ── 3.5) Multiband compressor + EQ ────────────────────────────────────────
# بنفصل الصوت ٣ نطاقات (واطي/وسط/عالي) ونضغط كل نطاق لوحده، فالصوت يطلع
# متوازن وواضح من غير ما الواطي يخنق العالي أو العكس — ده اللي بيدّي
# الإحساس «الإعلاني/الإذاعي» الاحترافي.

MULTIBAND_PRESETS: dict[str, dict] = {
    # متوازن وناعم — مناسب لمعظم الإعلانات
    "voice": {
        "crossovers": (250.0, 4000.0),
        "bands": [
            {"threshold_db": -24.0, "ratio": 3.0, "attack_ms": 15.0, "release_ms": 180.0, "gain_db": 0.0},
            {"threshold_db": -20.0, "ratio": 2.5, "attack_ms": 8.0, "release_ms": 120.0, "gain_db": 0.0},
            {"threshold_db": -26.0, "ratio": 2.0, "attack_ms": 3.0, "release_ms": 90.0, "gain_db": -1.5},
        ],
    },
    # دافي: باس أكتر + عالي أهدى (صوت رجالي عميق / إعلان فخم)
    "warm": {
        "crossovers": (220.0, 4500.0),
        "bands": [
            {"threshold_db": -22.0, "ratio": 2.5, "attack_ms": 20.0, "release_ms": 200.0, "gain_db": 2.0},
            {"threshold_db": -20.0, "ratio": 2.0, "attack_ms": 10.0, "release_ms": 130.0, "gain_db": 0.0},
            {"threshold_db": -28.0, "ratio": 2.5, "attack_ms": 3.0, "release_ms": 80.0, "gain_db": -3.0},
        ],
    },
    # حماسي/قوي: ضغط أعلى والوسط أبرز (إعلانات عروض)
    "punch": {
        "crossovers": (200.0, 3500.0),
        "bands": [
            {"threshold_db": -26.0, "ratio": 3.5, "attack_ms": 12.0, "release_ms": 150.0, "gain_db": 1.0},
            {"threshold_db": -22.0, "ratio": 3.5, "attack_ms": 5.0, "release_ms": 90.0, "gain_db": 1.5},
            {"threshold_db": -28.0, "ratio": 2.5, "attack_ms": 2.0, "release_ms": 70.0, "gain_db": -1.0},
        ],
    },
    # بث/راديو: متماسك وثابت طول الوقت
    "broadcast": {
        "crossovers": (300.0, 3500.0),
        "bands": [
            {"threshold_db": -24.0, "ratio": 4.0, "attack_ms": 10.0, "release_ms": 140.0, "gain_db": 0.0},
            {"threshold_db": -24.0, "ratio": 4.0, "attack_ms": 5.0, "release_ms": 100.0, "gain_db": 0.0},
            {"threshold_db": -30.0, "ratio": 3.0, "attack_ms": 2.0, "release_ms": 70.0, "gain_db": -2.0},
        ],
    },
}


def _lr4(data: np.ndarray, sr: int, fc: float, btype: str) -> np.ndarray:
    """فلتر Linkwitz-Riley رابع (زيرو-فاز عبر filtfilt) — بيسمح بإعادة تجميع
    النطاقات من غير تلوين (مجموع الواطي+الوسط+العالي ≈ الأصلي)."""
    nyq = sr / 2.0
    fc = min(max(fc, 1.0), nyq * 0.98)
    sos = butter(2, fc / nyq, btype=btype, output="sos")
    return sosfiltfilt(sos, data, axis=0)


def split_bands(
    data: np.ndarray, sr: int, crossovers: tuple[float, float] = (250.0, 4000.0)
) -> list[np.ndarray]:
    """يقسّم الصوت ٣ نطاقات: واطي / وسط / عالي."""
    c1, c2 = float(crossovers[0]), float(crossovers[1])
    if c1 > c2:
        c1, c2 = c2, c1
    low = _lr4(data, sr, c1, "lowpass")
    mid = _lr4(_lr4(data, sr, c1, "highpass"), sr, c2, "lowpass")
    high = _lr4(data, sr, c2, "highpass")
    return [low, mid, high]


def _envelope(
    rect: np.ndarray, sr: int, attack_ms: float, release_ms: float
) -> np.ndarray:
    """متتابع غلاف بمهاجمة سريعة وتحرير بطيء (dual one-pole)."""
    a = math.exp(-1000.0 / (sr * max(attack_ms, 0.05)))
    r = math.exp(-1000.0 / (sr * max(release_ms, 0.05)))
    fast = lfilter([1.0 - a], [1.0, -a], rect, axis=0)
    slow = lfilter([1.0 - r], [1.0, -r], rect, axis=0)
    return np.where(fast >= slow, fast, slow)


def compress_band(
    x: np.ndarray,
    sr: int,
    *,
    threshold_db: float = -20.0,
    ratio: float = 3.0,
    attack_ms: float = 8.0,
    release_ms: float = 120.0,
    gain_db: float = 0.0,
    knee_db: float = 6.0,
    max_reduction_db: float = 24.0,
) -> np.ndarray:
    """ضغط نطاق واحد (soft-knee) + مكسب ثابت (EQ) للنطاق."""
    if ratio <= 1.0:
        return x * (10.0 ** (gain_db / 20.0))

    env_db = 20.0 * np.log10(_envelope(np.abs(x), sr, attack_ms, release_ms) + 1e-12)
    over = env_db - threshold_db
    half = knee_db / 2.0
    slope = 1.0 - 1.0 / ratio
    gain_arr = np.where(
        over <= -half,
        0.0,
        np.where(
            over >= half,
            -slope * over,
            -slope * (over + half) ** 2 / (2.0 * knee_db),
        ),
    )
    gain_arr = np.clip(gain_arr, -max_reduction_db, 0.0) + gain_db
    return x * (10.0 ** (gain_arr / 20.0))


def multiband_compressor(data: np.ndarray, sr: int, preset: str = "voice") -> np.ndarray:
    """يضغط الصوت متعدد النطاقات حسب preset (voice/warm/punch/broadcast)."""
    cfg = MULTIBAND_PRESETS.get(preset)
    if not cfg or data.size == 0:
        return data
    bands = split_bands(data, sr, cfg["crossovers"])
    out = np.zeros_like(data, dtype=np.float64)
    for band, params in zip(bands, cfg["bands"]):
        out += compress_band(band, sr, **params)
    return out


def tilt_eq(
    data: np.ndarray,
    sr: int,
    *,
    low_db: float = 0.0,
    mid_db: float = 0.0,
    high_db: float = 0.0,
    crossovers: tuple[float, float] = (250.0, 4000.0),
) -> np.ndarray:
    """EQ بسيط ٣ نطاقات (مكاسب ثابتة، من غير ضغط)."""
    if low_db == mid_db == high_db == 0.0:
        return data
    bands = split_bands(data, sr, crossovers)
    out = np.zeros_like(data, dtype=np.float64)
    for band, gain_db in zip(bands, (low_db, mid_db, high_db)):
        out += band * (10.0 ** (gain_db / 20.0))
    return out


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


# ── 5) True-peak safety + Limiter ─────────────────────────────────────────


def peak_safety(data: np.ndarray, ceiling_db: float = -1.0) -> np.ndarray:
    """يضمن إن الذروة مش بتعدّي السقف (من غير تشويه)."""
    ceiling = 10.0 ** (ceiling_db / 20.0)
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    if peak > ceiling > 0:
        data = data * (ceiling / peak)
    return data


LIMITER_MARGIN_DB = 0.2  # هامش أمان للقمم اللي بين العيّنات (true-peak)


def limiter(
    data: np.ndarray,
    sr: int,
    ceiling_db: float = -1.0,
    release_ms: float = 90.0,
    lookahead_ms: float = 1.5,
) -> np.ndarray:
    """ليميتر بنظرة لقدّام: بيعمل **تحديد** للقمم العالية بدل ما يصغّر الصوت كله.

    الفرق عن `peak_safety`: ده بيمسك القمم المتفرقة (plosives/نقرات) ويحدّها
    للسقف بدل ما ينزّل مستوى المقطع بالكامل — فالجهارة الهدف توصل من غير ما
    تخسر 6dB.
    """
    if data.size == 0:
        return data
    ceiling = 10.0 ** (ceiling_db / 20.0)
    if ceiling <= 0:
        return data

    x = np.asarray(data, dtype=np.float64)
    peak = np.abs(x) if x.ndim == 1 else np.max(np.abs(x), axis=1)

    win = max(int(sr * lookahead_ms / 1000.0), 1)
    env = maximum_filter1d(peak, size=win, mode="nearest")
    target = np.minimum(1.0, ceiling / np.maximum(env, 1e-12))

    # مهاجمة سريعة (نزول) + تحرير بطيء (طلوع) عبر فلترَين one-pole
    a = math.exp(-1.0 / (sr * 0.0005))
    r = math.exp(-1.0 / (sr * max(release_ms, 1.0) / 1000.0))
    b_a, z_a = np.array([1.0 - a]), lfilter_zi([1.0 - a], [1.0, -a]) * target[0]
    b_r, z_r = np.array([1.0 - r]), lfilter_zi([1.0 - r], [1.0, -r]) * target[0]
    fast, _ = lfilter(b_a, [1.0, -a], target, zi=z_a)
    slow, _ = lfilter(b_r, [1.0, -r], target, zi=z_r)

    gain = np.minimum(np.minimum(fast, slow), target)
    y = x * gain if x.ndim == 1 else x * gain[:, None]
    return np.clip(y, -ceiling, ceiling)


def normalize_and_limit(
    data: np.ndarray,
    sr: int,
    target_lufs: float = -14.0,
    ceiling_db: float = -1.0,
    iterations: int = 3,
) -> np.ndarray:
    """يطبّع الجهارة للهدف ويحدّ القمم بـ limiter لحد ما يقرب للهدف."""
    if data.size == 0:
        return data
    for _ in range(max(int(iterations), 1)):
        data = normalize_loudness(data, sr, target_lufs)
        data = limiter(data, sr, ceiling_db=ceiling_db - LIMITER_MARGIN_DB)
        if measure_loudness(data, sr) >= target_lufs - 0.3:
            break
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
    multiband: str | None = None,
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
    if multiband:
        data = multiband_compressor(data, sr, multiband)
    if target_lufs is not None:
        # تطبيع الجهارة + تحديد القمم (limiter) بدل تصغير المقطع بالكامل
        data = normalize_and_limit(data, sr, target_lufs, true_peak_db)
    else:
        data = limiter(data, sr, ceiling_db=true_peak_db - LIMITER_MARGIN_DB)
    data = apply_fade(data, sr, fade_ms)
    if target_sr:
        data, sr = resample_audio(data, sr, target_sr)

    data = peak_safety(data, true_peak_db)
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
