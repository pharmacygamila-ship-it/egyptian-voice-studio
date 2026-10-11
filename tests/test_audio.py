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

from backend.audio.export import estimate_bitrate_kbps, export, media_type  # noqa: E402
from backend.audio.postprocess import (  # noqa: E402
    MULTIBAND_PRESETS,
    analyze,
    compress_band,
    deess,
    highpass,
    limiter,
    measure_loudness,
    multiband_compressor,
    normalize_and_limit,
    peak_safety,
    postprocess,
    split_bands,
    tilt_eq,
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


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2)))


# ── 8) ضغط/ EQ متعدد النطاقات ────────────────────────────────────────────
bands = split_bands(sig, sr0, (250.0, 4000.0))
recon = bands[0] + bands[1] + bands[2]
err = rms(recon - sig) / (rms(sig) + 1e-12)
check("split_bands: إعادة التجميع ≈ الأصلي", err < 0.05)
print(f"    -> خطأ إعادة التجميع {err * 100:.2f}%")

mb = multiband_compressor(sig, sr0, "voice")
check("multiband: نفس الطول/مفيش NaN", mb.shape == sig.shape and bool(np.all(np.isfinite(mb))))
check("multiband: غيّر الإشارة (ضغط فعلي)", not np.allclose(mb, sig))
check(
    "multiband: كل الـ presets شغّالة",
    all(np.all(np.isfinite(multiband_compressor(sig, sr0, p))) for p in MULTIBAND_PRESETS),
)

# ضغط مباشر لنطاق واحد
loud = 0.8 * np.sin(2 * np.pi * 300 * np.arange(sr0) / sr0)
quiet = 0.02 * np.sin(2 * np.pi * 300 * np.arange(sr0) / sr0)
c_loud = compress_band(loud, sr0, threshold_db=-20, ratio=4, attack_ms=5, release_ms=80)
c_quiet = compress_band(quiet, sr0, threshold_db=-20, ratio=4, attack_ms=5, release_ms=80)
check("compress_band: العالي اتضغط", rms(c_loud) < rms(loud) * 0.9)
check("compress_band: الواطي ما اتغيّرش", abs(rms(c_quiet) - rms(quiet)) < rms(quiet) * 0.02)
check("compress_band: ratio=1 = بدون تغيير", np.allclose(compress_band(loud, sr0, ratio=1.0), loud))
check(
    "compress_band: gain_db = EQ",
    rms(compress_band(quiet, sr0, ratio=1.0, gain_db=6.0)) > rms(quiet) * 1.9,
)

# EQ بسيط
check("tilt_eq: صفر = بدون تغيير", np.array_equal(tilt_eq(sig, sr0), sig))
check(
    "tilt_eq: الواطي زاد",
    band_energy(tilt_eq(sig, sr0, low_db=6.0), sr0, 60, 180)
    > band_energy(sig, sr0, 60, 180),
)

# السلسلة الكاملة مع multiband
out_mb = os.path.join(tmp, "out_mb.wav")
postprocess(in_path, out_mb, multiband="punch")
rep_mb = analyze(out_mb)
check("postprocess(multiband=punch): الجهارة ~ -14 LUFS", -15.0 <= rep_mb["lufs"] <= -13.0)

# ── 8.5) الليميتر مع قمم عالية (crest عالي) ─────────────────────────────
spiky = speech_like(sr0).copy()
_idx = np.linspace(0, spiky.size - 1, 12).astype(int)
spiky[_idx] += 3.0 * np.sign(spiky[_idx] + 1e-9)

ceil = 10 ** (-1.0 / 20)
lim = limiter(spiky, sr0, ceiling_db=-1.0)
check("limiter: الذروة ≤ السقف", float(np.max(np.abs(lim))) <= ceil + 1e-6)
check("limiter: بحدّ القمم مش يصغّر الكل", rms(lim) > rms(peak_safety(spiky, -1.0)))

nl = normalize_and_limit(spiky, sr0, -14.0, -1.0)
check("normalize_and_limit: الجهارة قربت -14", abs(measure_loudness(nl, sr0) + 14.0) < 1.5)
check("normalize_and_limit: الذروة ≤ -1dB", float(np.max(np.abs(nl))) <= 10 ** (-0.9 / 20))

sp_path = os.path.join(tmp, "spiky.wav")
sf.write(sp_path, spiky, sr0)
out_sp = os.path.join(tmp, "spiky_out.wav")
postprocess(sp_path, out_sp, target_lufs=-14.0)
rep_sp = analyze(out_sp)
check("postprocess (crest عالي): الجهارة ≥ -15.5", rep_sp["lufs"] >= -15.5)
check("postprocess (crest عالي): الذروة ≤ -1dB", rep_sp["peak_dbfs"] <= -1.0)
print(f"    -> قمم عالية: {rep_sp['lufs']:.1f} LUFS / {rep_sp['peak_dbfs']:.1f} dB")

# ── 9) تصدير MP3 ─────────────────────────────────────────────────────────
mp3_path = export(out_path, "mp3", bitrate=192)
check("export mp3: الملف اتكتب", os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 1000)
with open(mp3_path, "rb") as fh:
    head = fh.read(3)
check("export mp3: بصمة MP3 صحيحة", head[:3] == b"ID3" or head[0] == 0xFF)
back, _ = sf.read(mp3_path, always_2d=False, dtype="float32")
check("export mp3: قابل للقراءة", back.size > 0)
check("export mp3: media_type", media_type(mp3_path) == "audio/mpeg")
mp3_320 = export(out48, "mp3", bitrate=320)
check("export mp3 320: الملف اتكتب", os.path.exists(mp3_320) and os.path.getsize(mp3_320) > 1000)
check("export mp3 320: معدل البت أعلى من 192k", estimate_bitrate_kbps(mp3_320) > 200)
check("export wav: بيرجّع نفس المسار", export(out_path, "wav") == out_path)
try:
    export(out_path, "ogg")
    check("export: يرفض صيغة غلط", False)
except ValueError:
    check("export: يرفض صيغة غلط", True)

print(f"\n==> {total} اختبار |", "كله تمام ✅" if ok else "فيه فشل ❌")
raise SystemExit(0 if ok else 1)
