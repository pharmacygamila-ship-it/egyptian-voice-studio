"""تجهيز تسجيلات العميل لمسار fine-tune (استنساخ «نفس الأداء الصوتي»).

بياخد مجلد تسجيلات + نصوصها، وبيطلع:
    dataset/
      clips/       مقاطع منظّفة 24kHz أحادية
      train.jsonl  بيانات التدريب
      val.jsonl    بيانات التحقق
      report.json  تقرير الجودة

طريقة النصوص (واحدة من الاتنين):
    1) ملف نصوص: سطر لكل ملف →  "الملف.wav|النص هنا"  (أو بـ Tab)
    2) ملف .txt جنب كل تسجيل بنفس الاسم

مثال:
    .venv\\Scripts\\python.exe finetune\\prepare_dataset.py \\
        --in data/voice_client --transcripts data/voice_client/transcripts.txt \\
        --out finetune/dataset
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import random
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.audio.postprocess import (  # noqa: E402
    highpass,
    normalize_loudness,
    peak_safety,
    resample_audio,
    trim_silence,
)

AUDIO_EXT = (".wav", ".flac", ".mp3", ".ogg", ".m4a")


def load_transcripts(path: str) -> dict[str, str]:
    """يقرأ ملف نصوص (stem → نص). يفصل بـ | أو Tab."""
    mapping: dict[str, str] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            if "\t" in line:
                name, _, text = line.partition("\t")
            elif "|" in line:
                name, _, text = line.partition("|")
            else:
                continue
            stem = os.path.splitext(os.path.basename(name.strip()))[0]
            mapping[stem] = text.strip()
    return mapping


def collect(in_dir: str, transcripts: str | None) -> list[tuple[str, str]]:
    """يرجّع قائمة (مسار الملف، النص)."""
    files = sorted(
        p for p in glob.glob(os.path.join(in_dir, "*"))
        if os.path.splitext(p)[1].lower() in AUDIO_EXT
    )
    table = load_transcripts(transcripts) if transcripts else {}
    items: list[tuple[str, str]] = []
    for path in files:
        stem = os.path.splitext(os.path.basename(path))[0]
        text = table.get(stem)
        if text is None:  # ملف .txt جنب التسجيل
            side = os.path.join(in_dir, stem + ".txt")
            if os.path.exists(side):
                with open(side, encoding="utf-8") as fh:
                    text = fh.read().strip()
        items.append((path, text or ""))
    return items


def clean_clip(
    data: np.ndarray, sr: int, *, target_sr: int = 24000, lufs: float = -20.0
) -> np.ndarray:
    """تنضيف المقطع: أحادي → تشذيب → high-pass → إعادة تنميط → تطبيع جهارة."""
    if data.ndim > 1:
        data = data.mean(axis=1)
    data = trim_silence(data, sr)
    if data.size == 0:
        return data
    data = highpass(data, sr, 80.0)
    data, sr = resample_audio(data, sr, target_sr)
    data = normalize_loudness(data, sr, lufs)
    data = peak_safety(data, -1.0)
    return np.clip(data, -1.0, 1.0)


def prepare(
    in_dir: str,
    out_dir: str,
    transcripts: str | None = None,
    *,
    target_sr: int = 24000,
    min_sec: float = 2.0,
    max_sec: float = 20.0,
    lufs: float = -20.0,
    val_ratio: float = 0.1,
    seed: int = 42,
) -> dict:
    """يجهّز الداتاسِت ويرجّع تقرير."""
    items = collect(in_dir, transcripts)
    if not items:
        raise ValueError(f"مفيش ملفات صوت في {in_dir}")

    clips_dir = os.path.join(out_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    kept: list[dict] = []
    dropped: list[dict] = []

    for path, text in items:
        text = (text or "").strip()
        if not text:
            dropped.append({"file": os.path.basename(path), "reason": "نص فاضي"})
            continue
        try:
            data, sr = sf.read(path, always_2d=False, dtype="float64")
        except Exception as exc:  # noqa: BLE001
            dropped.append({"file": os.path.basename(path), "reason": f"خطأ قراءة: {exc}"})
            continue

        data = clean_clip(data, sr, target_sr=target_sr, lufs=lufs)
        dur = len(data) / target_sr if target_sr else 0.0
        if dur < min_sec:
            dropped.append({"file": os.path.basename(path), "reason": f"قصير ({dur:.1f}s)"})
            continue
        if dur > max_sec:
            dropped.append({"file": os.path.basename(path), "reason": f"طويل ({dur:.1f}s)"})
            continue

        name = os.path.splitext(os.path.basename(path))[0] + ".wav"
        out_path = os.path.join(clips_dir, name)
        sf.write(out_path, data, target_sr)
        kept.append(
            {"audio": os.path.join("clips", name), "text": text, "duration": round(dur, 3)}
        )

    if not kept:
        raise ValueError("كل المقاطع اترفضت — راجع التقرير")

    rng = random.Random(seed)
    rng.shuffle(kept)
    n_val = max(1, int(len(kept) * val_ratio)) if len(kept) >= 2 else 0
    val, train = kept[:n_val], kept[n_val:]

    def write_jsonl(path: str, rows: list[dict]) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    write_jsonl(os.path.join(out_dir, "train.jsonl"), train)
    write_jsonl(os.path.join(out_dir, "val.jsonl"), val)

    durations = [k["duration"] for k in kept]
    report = {
        "input_clips": len(items),
        "kept": len(kept),
        "dropped": len(dropped),
        "dropped_details": dropped,
        "train": len(train),
        "val": len(val),
        "total_seconds": round(sum(durations), 2),
        "mean_seconds": round(sum(durations) / len(durations), 2),
        "target_sr": target_sr,
        "target_lufs": lufs,
    }
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="تجهيز داتاسِت fine-tune")
    ap.add_argument("--in", dest="in_dir", required=True, help="مجلد التسجيلات")
    ap.add_argument("--out", dest="out_dir", default="finetune/dataset")
    ap.add_argument("--transcripts", help="ملف نصوص (stem|text أو stem<Tab>text)")
    ap.add_argument("--sr", type=int, default=24000)
    ap.add_argument("--min-sec", type=float, default=2.0)
    ap.add_argument("--max-sec", type=float, default=20.0)
    ap.add_argument("--lufs", type=float, default=-20.0)
    ap.add_argument("--val-ratio", type=float, default=0.1)
    args = ap.parse_args()

    report = prepare(
        args.in_dir, args.out_dir, args.transcripts,
        target_sr=args.sr, min_sec=args.min_sec, max_sec=args.max_sec,
        lufs=args.lufs, val_ratio=args.val_ratio,
    )
    print("[✓] تم تجهيز الداتاسِت:")
    print(f"    بتدريب: {report['train']} | تحقق: {report['val']} | مرفوض: {report['dropped']}")
    print(f"    إجمالي: {report['total_seconds']}s | متوسط: {report['mean_seconds']}s/مقطع")
    print(f"    SR: {report['target_sr']} | LUFS: {report['target_lufs']}")
    if report["dropped_details"]:
        print("    المرفوض:")
        for d in report["dropped_details"][:10]:
            print(f"      - {d['file']}: {d['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
