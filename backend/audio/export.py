"""تصدير الصوت النهائي: WAV أو MP3 (من غير ffmpeg).

- MP3 عبر `lameenc` (بيحمل LAME جواه) ولو مش موجود بيرجع لـ libsndfile.
- كل حاجة محلية بالكامل.
"""
from __future__ import annotations

import os

import numpy as np
import soundfile as sf

# معدّلات MP3 المدعومة (Hz)
MP3_RATES = (8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000)


def _encode_mp3_lameenc(data: np.ndarray, sr: int, bitrate: int) -> bytes:
    import lameenc

    enc = lameenc.Encoder()
    enc.set_bit_rate(int(bitrate))
    enc.set_in_sample_rate(int(sr))
    enc.set_channels(1 if data.ndim == 1 else data.shape[1])
    enc.set_quality(2)  # 2 = جودة عالية (0 أبطأ/أحسن)

    pcm = (np.clip(data, -1.0, 1.0) * 32767.0).astype("<i2")
    return bytes(enc.encode(pcm.tobytes())) + bytes(enc.flush())


def _nearest_rate(sr: int) -> int:
    return min(MP3_RATES, key=lambda r: abs(r - sr))


def wav_to_mp3(
    wav_path: str, mp3_path: str | None = None, *, bitrate: int = 192
) -> str:
    """يحوّل ملف WAV لـ MP3. بيرجّع مسار ملف الـ MP3."""
    data, sr = sf.read(wav_path, always_2d=False, dtype="float32")
    mp3_path = mp3_path or (os.path.splitext(wav_path)[0] + ".mp3")

    if data.size == 0:
        raise ValueError("الملف فاضي — مفيش صوت يتصدّر")

    if sr not in MP3_RATES:
        from backend.audio.postprocess import resample_audio

        data, sr = resample_audio(data, sr, _nearest_rate(sr))

    try:
        blob = _encode_mp3_lameenc(data, sr, bitrate)
    except ImportError:
        # بديل: libsndfile (لو النسخة تدعم كتابة MP3)
        sf.write(mp3_path, data, sr, format="MP3", bitrate_mode="VBR")
        return mp3_path

    with open(mp3_path, "wb") as fh:
        fh.write(blob)
    return mp3_path


def export(path: str, fmt: str = "wav", *, bitrate: int = 192) -> str:
    """يصدّر الملف بالصيغة المطلوبة. WAV بيرجّعه زي ما هو، MP3 يحوّله."""
    fmt = (fmt or "wav").lower().lstrip(".")
    if fmt in ("wav", "wave"):
        return path
    if fmt in ("mp3", "mpeg3"):
        return wav_to_mp3(path, bitrate=bitrate)
    raise ValueError(f"صيغة غير مدعومة: {fmt} (المتاح: wav, mp3)")


def media_type(path: str) -> str:
    """نوع الـ MIME حسب امتداد الملف."""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    return {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "flac": "audio/flac",
        "ogg": "audio/ogg",
    }.get(ext, "application/octet-stream")


def estimate_bitrate_kbps(path: str) -> float:
    """تقدير معدّل البت التقريبي (kbps) — للتقرير."""
    size_bits = os.path.getsize(path) * 8
    data, sr = sf.read(path, always_2d=False, dtype="float32")
    seconds = (len(data) / sr) if sr else 0.0
    if seconds <= 0:
        return float("nan")
    return round(size_bits / seconds / 1000.0, 1)
