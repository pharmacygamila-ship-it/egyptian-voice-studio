"""توليد دفعي لكل نصوص الإعلانات في data/scripts.

تسمية الملفات:
    ad1.txt            → يستخدم الصوت الافتراضي
    ad2__Yasmin.txt    → يستخدم صوت Yasmin

أمثلة:
    # محلياً (عبر السيرفر السحابي أو الـ Space)
    .venv\\Scripts\\python.exe batch_generate.py

    # على Colab/Kaggle (GPU محلي)
    TTS_ENGINE=local python batch_generate.py --speaker Sayed --zip ads.zip

    # معاينة من غير توليد
    .venv\\Scripts\\python.exe batch_generate.py --dry-run
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.audio.export import export  # noqa: E402
from backend.audio.postprocess import analyze, postprocess  # noqa: E402
from backend.engine.base import SynthRequest  # noqa: E402
from backend.engine.factory import build_engine  # noqa: E402
from backend.text.normalize import normalize_for_tts  # noqa: E402


def parse_name(path: str) -> tuple[str, str | None]:
    """ad2__Yasmin.txt → ("ad2", "Yasmin")"""
    base = os.path.splitext(os.path.basename(path))[0]
    if "__" in base:
        name, speaker = base.split("__", 1)
        return name.strip(), speaker.strip()
    return base, None


def main() -> int:
    ap = argparse.ArgumentParser(description="توليد دفعي لنصوص الإعلانات")
    ap.add_argument("--dir", default=os.path.join("data", "scripts"))
    ap.add_argument("--out", default=os.path.join("data", "outputs"))
    ap.add_argument("--speaker", default="Sayed")
    ap.add_argument("--steps", type=int, default=64)
    ap.add_argument("--guidance", type=float, default=2.5)
    ap.add_argument("--speed", type=float, default=0.95)
    ap.add_argument("--zip", dest="zip_path", help="يضغط كل النواتج في ملف zip")
    ap.add_argument("--diacritics", action="store_true",
                    help="تشكيل الكلمات الملتبسة (اختياري)")
    ap.add_argument("--multiband", choices=["voice", "warm", "punch", "broadcast"],
                    help="ضغط/EQ متعدد النطاقات (اختياري)")
    ap.add_argument("--mp3", action="store_true", help="صدّر MP3 بدل WAV")
    ap.add_argument("--bitrate", type=int, default=192, help="معدّل بت MP3 (kbps)")
    ap.add_argument("--dry-run", action="store_true", help="يعرض الخطة من غير توليد")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, "*.txt")))
    if not files:
        print(f"مفيش ملفات .txt في {args.dir}")
        return 1

    engine = None if args.dry_run else build_engine()
    if engine:
        print(f"[i] المحرك: {engine.name}")

    os.makedirs(args.out, exist_ok=True)
    produced: list[str] = []

    for path in files:
        name, speaker = parse_name(path)
        speaker = speaker or args.speaker
        with open(path, encoding="utf-8") as fh:
            text = normalize_for_tts(fh.read().strip(), diacritics=args.diacritics)
        out = os.path.join(args.out, f"{name}.wav")

        if args.dry_run:
            ext = "mp3" if args.mp3 else "wav"
            print(f"[dry] {os.path.basename(path):<24} → {name}.{ext}  (صوت: {speaker})")
            continue

        print(f"[..] {os.path.basename(path)}  (صوت: {speaker})")
        try:
            req = SynthRequest(
                text=text, speaker=speaker, steps=args.steps,
                guidance=args.guidance, speed=args.speed,
                normalize=False,
            )
            path_out = engine.synthesize(req, out)
            postprocess(path_out, multiband=args.multiband)
            if args.mp3:
                path_out = export(path_out, "mp3", bitrate=args.bitrate)
            produced.append(path_out)
            rep = analyze(path_out)
            print(f"     ✓ {path_out}  ({rep['lufs']:.1f} LUFS)")
        except Exception as exc:  # noqa: BLE001
            print(f"     ✗ فشل: {exc}")

    if args.zip_path and produced:
        with zipfile.ZipFile(args.zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in produced:
                z.write(p, os.path.basename(p))
        print(f"[✓] تم الضغط: {args.zip_path} ({len(produced)} ملف)")

    print(f"خلصنا — {len(produced)} ملف" if not args.dry_run else "معاينة بس (dry-run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
