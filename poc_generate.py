"""PoC — يولّد صوت مصري من غير GPU (عبر الـ Space الجاهز).

أمثلة:
    .venv\\Scripts\\python.exe poc_generate.py --speaker Sayed --text "أهلاً بيك في تطبيقنا"
    .venv\\Scripts\\python.exe poc_generate.py --speaker Yasmin --text-file data/scripts/ad1.txt --out data/outputs/ad1.wav
    .venv\\Scripts\\python.exe poc_generate.py --speaker Sayed --ref-audio my.wav --ref-text "النص" --text "كلام جديد"
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.audio.export import export  # noqa: E402
from backend.audio.postprocess import analyze, postprocess  # noqa: E402
from backend.engine.base import SynthRequest  # noqa: E402
from backend.engine.remote_voicetut import RemoteVoiceTutEngine  # noqa: E402
from backend.engine.server_client import ServerVoiceTutEngine  # noqa: E402
from backend.text.normalize import normalize_for_tts  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="VoiceTut-TTS PoC (عامية مصرية)")
    ap.add_argument("--speaker", default="Sayed", help="اسم الصوت الجاهز")
    ap.add_argument("--text", help="النص المطلوب نطقه")
    ap.add_argument("--text-file", help="ملف نصي فيه النص (UTF-8)")
    ap.add_argument("--ref-audio", help="مقطع مرجعي للاستنساخ")
    ap.add_argument("--ref-text", default="", help="نص المقطع المرجعي")
    ap.add_argument("--out", default="data/outputs/out.wav")
    ap.add_argument("--steps", type=int, default=64)
    ap.add_argument("--guidance", type=float, default=2.5)
    ap.add_argument("--speed", type=float, default=0.95)
    ap.add_argument("--no-normalize", action="store_true", help="يعطّل تطبيع النص")
    ap.add_argument("--diacritics", action="store_true",
                    help="تشكيل الكلمات الملتبسة (اختياري)")
    ap.add_argument("--no-postprocess", action="store_true")
    ap.add_argument("--multiband", choices=["voice", "warm", "punch", "broadcast"],
                    help="ضغط/EQ متعدد النطاقات (اختياري)")
    ap.add_argument("--mp3", action="store_true", help="صدّر MP3 بدل WAV")
    ap.add_argument("--bitrate", type=int, default=192, help="معدّل بت MP3 (kbps)")
    ap.add_argument("--server", help="رابط سيرفر GPU بتاعنا (يشغّل المحرك 'server')")
    ap.add_argument("--token", help="توكن السيرفر (TTS_SERVER_TOKEN)")
    ap.add_argument("--engine", choices=["remote", "server", "local"],
                    help="تحديد المحرك صراحةً (افتراضي: remote، أو server لو --server موجود)")
    args = ap.parse_args()

    if args.text_file:
        with open(args.text_file, encoding="utf-8") as fh:
            text = fh.read().strip()
    elif args.text:
        text = args.text
    else:
        ap.error("لازم تحدد --text أو --text-file")

    clean = normalize_for_tts(text, diacritics=args.diacritics) if not args.no_normalize else text
    print(f"[i] الصوت: {args.speaker or args.ref_audio}")
    print(f"[i] النص: {clean[:120]}{'...' if len(clean) > 120 else ''}")

    engine_kind = args.engine or ("server" if args.server else "remote")
    if engine_kind == "server":
        engine = ServerVoiceTutEngine(base_url=args.server, token=args.token)
    elif engine_kind == "local":
        from backend.engine.local_voicetut import LocalVoiceTutEngine

        engine = LocalVoiceTutEngine()
    else:
        engine = RemoteVoiceTutEngine()
    print(f"[i] المحرك: {engine.name}")

    req = SynthRequest(
        text=clean,
        speaker=None if args.ref_audio else args.speaker,
        ref_audio=args.ref_audio,
        ref_text=args.ref_text,
        steps=args.steps,
        guidance=args.guidance,
        speed=args.speed,
        normalize=False,
    )

    print("[i] جاري التوليد (الـ Space المجاني ممكن يستغرق شوية)...")
    path = engine.synthesize(req, args.out)
    if not args.no_postprocess:
        path = postprocess(path, multiband=args.multiband)
    if args.mp3:
        path = export(path, "mp3", bitrate=args.bitrate)
    rep = analyze(path)
    print(f"[✓] تم الحفظ: {path}")
    print(
        f"[i] {rep['seconds']:.2f} ثانية | {rep['lufs']:.1f} LUFS | "
        f"ذروة {rep['peak_dbfs']:.1f} dB | {int(rep['sr'])}Hz"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
