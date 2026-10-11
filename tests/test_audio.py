"""اختبارات معالجة الصوت الاحترافية (LUFS + de-esser + high-pass).

    .venv\\Scripts\\python.exe tests\\test_audio.py
"""
from __future__ import annotations

import os
import sys
import tempfile

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from backend.audio.postprocess import (  # noqa: E402
    analyze,
    deess,
    highpass,
    measure_loudness,
    peak_safety,
    postprocess,
)

ok = True
total = 0


def check(label: str, cond: bool) -> None:
    global ok, total
    total += 1
    ok = ok and cond
    print(f"[{'PASS' if cond else 'FAIL'}] {label}")


def band_energy(x: np.ndarray, sr: int, low: float, high: float) -> float:
    sos = butter(2, [low / (sr / 2), high / (sr / 2)], btype="band", output="sos")
    y = sosfilt(sos, x, axis=0)
    return float(np.sqrt(np.mean(y**2)))


def speech_like(sr: int, seconds: float = 3.0, seed: int = 7) -> np.ndarray:
    """إشارة شبه كلام: نغمة + مظروف مقاطع + صفير سين."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(sr * seconds)) / sr
    env = 0.5 * (1.0 + np.sin(2 * np.pi * 3.0 * t))  # مقاطع
    voice = 0.4 * env * np.sin(2 * np.pi * 180 * t + 0.3 * np.sin(2 * np.pi * 2 * t))
    sib = 0.25 * 1.0 * (np.sin(2 * np.pi * 7000 * t) > 0.7) * np.sin(2 * np.pi * 7000 * t)
    noise = 0.01 * rng.standard_normal(t.size)
    return (voice + sib + noise).astype(np.float64)


tmp = tempfile.mkdtemp(prefix="tts_audio_")
sr0 = 24000
sig = speech_like(sr0)
in_path = os.path.join(tmp, "in.wav")
out_path = os.path.join(tmp, "out.wav")
sf.write(in_path, sig, sr0)

# ── 1) السلسلة الكاملة ───────────────────────────────────────────────────
postprocess(in_path, out_path)
report = analyze(out_path)
check("postprocess: الملف اتكتب", os.path.exists(out_path) and os.path.getsize(out_path) > 1000)
check("postprocess: الجهارة ~ -14 LUFS", -15.0 <= report["lufs"] <= -13.0)
check("postprocess: الذروة <= -0.9 dBTP", report["peak_dbfs"] <= -0.9)
check(f"postprocess: SR اتحفظ ({sr0})", int(report["sr"]) == sr0)
print(f"    -> LUFS={report['lufs']:.2f}, peak={report['peak_dbfs']:.2f}dB, {report['seconds']:.2f}s")

# ── 2) إعادة التنميط لـ 48kHz ────────────────────────────────────────────
out48 = os.path.join(tmp, "out48.wav")
postprocess(in_path, out48, target_sr=48000)
check("postprocess: target_sr=48000", int(analyze(out48)["sr"]) == 48000)

# ── 3) High-pass ─────────────────────────────────────────────────────────
t = np.arange(sr0 * 2) / sr0
mixed = 0.5 * np.sin(2 * np.pi * 40 * t) + 0.5 * np.sin(2 * np.pi * 1000 * t)
hp = highpass(mixed, sr0, 80.0)
low_before, low_after = band_energy(mixed, sr0, 20, 60), band_energy(hp, sr0, 20, 60)
high_before, high_after = band_energy(mixed, sr0, 900, 1100), band_energy(hp, sr0, 900, 1100)
check("highpass: الواطي اتخفّض", low_after < low_before * 0.2)
check("highpass: العالي فَضَل", high_after > high_before * 0.8)

# ── 4) De-esser ──────────────────────────────────────────────────────────
sib_before = band_energy(sig, sr0, 5000, 9000)
de = deess(sig, sr0)
sib_after = band_energy(de, sr0, 5000, 9000)
check("de-esser: الصفير اتخفّض", sib_after < sib_before * 0.7)
print(f"    -> sibilance {sib_before:.4f} → {sib_after:.4f}")

# ── 5) True-peak safety ──────────────────────────────────────────────────
hot = np.array([0.0, 0.9, -1.4, 0.3])  # ذروة 1.4 > سقف
lim = peak_safety(hot, -1.0)
check("peak_safety: الذروة اتحصرت", float(np.max(np.abs(lim))) <= 10 ** (-1.0 / 20) + 1e-6)

# ── 6) ملف ساكت ما يكسرش ─────────────────────────────────────────────────
silent = os.path.join(tmp, "silent.wav")
sf.write(silent, np.zeros(sr0, dtype=np.float64), sr0)
try:
    postprocess(silent, silent)
    check("postprocess: الصوت الساكت اتعالج من غير كسر", True)
except Exception as exc:  # noqa: BLE001
    check(f"postprocess: الصوت الساكت اتعالج من غير كسر ({exc})", False)

# ── 7) القياس المباشر ───────────────────────────────────────────────────
check("measure_loudness: يرجّع رقم", np.isfinite(measure_loudness(sig, sr0)))

print(f"\n==> {total} اختبار |", "كله تمام ✅" if ok else "فيه فشل ❌")
raise SystemExit(0 if ok else 1)
