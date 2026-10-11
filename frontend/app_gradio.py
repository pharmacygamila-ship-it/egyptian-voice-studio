"""واجهة Gradio لتوليد/استنساخ الصوت المصري (بديل/إضافة للواجهة الويب).

التشغيل:
    .venv\\Scripts\\python.exe frontend\\app_gradio.py
    .venv\\Scripts\\python.exe frontend\\app_gradio.py --share --port 7860

بتستخدم نفس المحركات والمعالجة بتاعة الـ API (تطبيع + تشكيل + multiband + MP3).
"""
from __future__ import annotations

import argparse
import inspect
import os
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.audio.export import export  # noqa: E402
from backend.audio.postprocess import analyze, postprocess  # noqa: E402
from backend.engine.base import SynthRequest  # noqa: E402
from backend.engine.factory import build_engine  # noqa: E402
from backend.text.normalize import normalize_for_tts  # noqa: E402

OUTPUT_DIR = os.getenv("TTS_OUTPUT_DIR", os.path.join(ROOT, "data", "outputs"))
MULTIBAND_CHOICES = ["", "voice", "warm", "punch", "broadcast"]
LUFS_CHOICES = [-16, -14, -12, -9]
FALLBACK_SPEAKERS = [
    "Sayed", "Yasmin", "Mohamed", "Omar", "Ahmed", "Aly", "Hossam",
    "Kamal", "Zaki", "Essam", "Abdelrahman", "Abdullah",
    "Asmaa", "Esraa", "Hanan", "Sarah", "Omnia",
]

RTL_CSS = ".gradio-container { direction: rtl; text-align: right; }"

_ENGINE = None


def _blocks_kwargs() -> dict:
    """theme/css على Blocks في Gradio 4/5، وعلى launch في Gradio 6."""
    import gradio as gr

    kw: dict = {"title": "استوديو الصوت المصري"}
    try:
        params = inspect.signature(gr.Blocks.__init__).parameters
        if "theme" in params:
            kw["theme"] = gr.themes.Soft()
        if "css" in params:
            kw["css"] = RTL_CSS
    except (TypeError, ValueError):
        pass
    return kw


def _launch_kwargs() -> dict:
    import gradio as gr

    kw: dict = {}
    try:
        params = inspect.signature(gr.Blocks.launch).parameters
        if "theme" in params:
            kw["theme"] = gr.themes.Soft()
        if "css" in params:
            kw["css"] = RTL_CSS
    except (TypeError, ValueError):
        pass
    return kw


def get_engine():
    """ينشئ المحرك مرة واحدة (حسب TTS_ENGINE)."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = build_engine()
    return _ENGINE


def list_speakers() -> list[str]:
    """يجيب أسماء الأصوات الجاهزة (مع بديل ثابت لو المحرك مش جاهز)."""
    try:
        names = [s.name for s in get_engine().list_speakers()]
        return names or list(FALLBACK_SPEAKERS)
    except Exception:  # noqa: BLE001
        return list(FALLBACK_SPEAKERS)


def prepare_text(text: str, normalize: bool, diacritics: bool) -> str:
    """تطبيع النص المصري (نفس منطق الـ API)."""
    return normalize_for_tts(text, diacritics=diacritics) if normalize else text


def _out_path(prefix: str) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return os.path.join(OUTPUT_DIR, f"{prefix}_{uuid.uuid4().hex[:8]}.wav")


def _finish(path: str, postprocess_on: bool, lufs: float, multiband: str, fmt: str) -> tuple[str, str]:
    """معالجة + تصدير + تقرير مختصر."""
    if postprocess_on:
        path = postprocess(path, target_lufs=float(lufs), multiband=(multiband or None))
    path = export(path, fmt)
    rep = analyze(path)
    info = (
        f"{rep['seconds']:.2f} ثانية · {rep['lufs']:.1f} LUFS · "
        f"ذروة {rep['peak_dbfs']:.1f} dB · {int(rep['sr'])}Hz · {fmt.upper()}"
    )
    return path, info


def synth_ui(
    text, speaker, steps, guidance, speed,
    normalize, diacritics, postprocess_on, lufs, multiband, fmt,
):
    import gradio as gr

    if not (text or "").strip():
        raise gr.Error("اكتب النص الأول")

    clean = prepare_text(text, normalize, diacritics)
    out = _out_path("tts")
    req = SynthRequest(
        text=clean, speaker=speaker, steps=int(steps),
        guidance=float(guidance), speed=float(speed), normalize=False,
    )
    try:
        path = get_engine().synthesize(req, out)
    except Exception as exc:  # noqa: BLE001
        raise gr.Error(f"فشل التوليد: {exc}") from exc
    return _finish(path, postprocess_on, lufs, multiband, fmt)


def clone_ui(
    ref_audio, ref_text, text, steps, guidance, speed,
    normalize, diacritics, postprocess_on, lufs, multiband, fmt,
):
    import gradio as gr

    if not ref_audio:
        raise gr.Error("ارفع مقطع صوتي مرجعي")
    if not (text or "").strip():
        raise gr.Error("اكتب النص المطلوب")

    clean = prepare_text(text, normalize, diacritics)
    out = _out_path("clone")
    req = SynthRequest(
        text=clean, ref_audio=ref_audio, ref_text=ref_text or "",
        steps=int(steps), guidance=float(guidance), speed=float(speed),
        normalize=False,
    )
    try:
        path = get_engine().clone(req, out)
    except Exception as exc:  # noqa: BLE001
        raise gr.Error(f"فشل الاستنساخ: {exc}") from exc
    return _finish(path, postprocess_on, lufs, multiband, fmt)


def build_interface(speakers: list[str] | None = None):
    """يبني واجهة Gradio (يرجّع Blocks)."""
    import gradio as gr

    speakers = speakers or list_speakers()

    with gr.Blocks(**_blocks_kwargs()) as demo:
        gr.Markdown(
            "# 🎙️ استوديو الصوت المصري\n"
            "توليد واستنساخ بالعامية المصرية + معالجة بجودة بث (LUFS + Multiband + MP3)."
        )

        with gr.Accordion("⚙️ إعدادات عامة", open=False):
            fmt = gr.Dropdown(["wav", "mp3"], value="wav", label="صيغة الملف الناتج")
            multiband = gr.Dropdown(
                MULTIBAND_CHOICES, value="", label="ضغط/EQ متعدد النطاقات"
            )
            lufs = gr.Dropdown(LUFS_CHOICES, value=-14, label="جهارة الهدف (LUFS)")
            postprocess_on = gr.Checkbox(True, label="معالجة صوتية احترافية")
            diacritics = gr.Checkbox(False, label="تشكيل الكلمات الملتبسة")
            normalize = gr.Checkbox(True, label="تطبيع النص المصري")

        with gr.Tab("🔊 توليد بصوت جاهز"):
            text = gr.Textbox(lines=4, label="النص (عامية مصرية)")
            speaker = gr.Dropdown(
                speakers, value=(speakers[0] if speakers else "Sayed"), label="الصوت"
            )
            with gr.Row():
                steps = gr.Slider(8, 64, value=64, step=1, label="خطوات التوليد")
                guidance = gr.Slider(1.0, 5.0, value=2.5, step=0.1, label="قوة التوجيه")
                speed = gr.Slider(0.5, 2.0, value=0.95, step=0.05, label="السرعة")
            go = gr.Button("🔊 توليد", variant="primary")
            out_audio = gr.Audio(label="الناتج", type="filepath")
            out_info = gr.Textbox(label="التقرير", interactive=False)
            go.click(
                synth_ui,
                [text, speaker, steps, guidance, speed,
                 normalize, diacritics, postprocess_on, lufs, multiband, fmt],
                [out_audio, out_info],
            )

        with gr.Tab("🧬 استنساخ صوت"):
            ref = gr.Audio(label="المقطع المرجعي (wav/mp3)", type="filepath")
            ref_text = gr.Textbox(label="نص المقطع المرجعي (اختياري — بيحسّن الدقة)")
            text2 = gr.Textbox(lines=4, label="النص المطلوب")
            go2 = gr.Button("🧬 استنساخ", variant="primary")
            out_audio2 = gr.Audio(label="الناتج", type="filepath")
            out_info2 = gr.Textbox(label="التقرير", interactive=False)
            go2.click(
                clone_ui,
                [ref, ref_text, text2, steps, guidance, speed,
                 normalize, diacritics, postprocess_on, lufs, multiband, fmt],
                [out_audio2, out_info2],
            )

        gr.Markdown("> ⚖️ محتاج موافقة **مكتوبة** من صاحب أي صوت حقيقي قبل الاستنساخ.")

    return demo


def main() -> int:
    ap = argparse.ArgumentParser(description="واجهة Gradio للصوت المصري")
    ap.add_argument("--port", type=int, default=7860)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--share", action="store_true", help="رابط عام مؤقّت (Gradio share)")
    args = ap.parse_args()

    demo = build_interface()
    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        **_launch_kwargs(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
