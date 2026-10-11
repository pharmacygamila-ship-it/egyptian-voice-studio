"""واجهة Gradio — **مركز تحكم كامل** لاستوديو الصوت المصري.

كل حاجة من جوّه التطبيق (من غير كود ولا سطر أوامر):
  - 🔊 توليد بصوت جاهز + معاينة النطق بعد التطبيع
  - 🧬 استنساخ صوت من مقطع مرجعي
  - 📦 توليد دفعي من ملفات نصية → ملف zip
  - 🔎 فاحص النطق (ASR): يفرّغ الناتج ويقارنه بالنص بالحرف
  - 📖 قاموس النطق المخصّص (إضافة/تعديل/حفظ)
  - ⚙️ الإعدادات: نوع المحرك/السيرفر/التوكن/الموديل — وتُحفظ تلقائيًا

التشغيل:
    .venv\\Scripts\\python.exe frontend\\app_gradio.py
    .venv\\Scripts\\python.exe frontend\\app_gradio.py --share --port 7860
    .venv\\Scripts\\python.exe frontend\\app_gradio.py --engine local   # على Colab/GPU
"""
from __future__ import annotations

import argparse
import inspect
import os
import sys
import uuid
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend import store  # noqa: E402
from backend.audio.export import export  # noqa: E402
from backend.audio.postprocess import analyze, postprocess  # noqa: E402
from backend.engine.base import SynthRequest  # noqa: E402
from backend.engine.factory import build_engine  # noqa: E402
from backend.text.normalize import normalize_for_tts  # noqa: E402

OUTPUT_DIR = os.getenv("TTS_OUTPUT_DIR", os.path.join(ROOT, "data", "outputs"))
MULTIBAND_CHOICES = ["", "voice", "warm", "punch", "broadcast"]
LUFS_CHOICES = [-16, -14, -12, -9]
ENGINE_CHOICES = ["remote", "server", "local"]
ASR_CHOICES = ["tiny", "base", "small", "medium", "large-v3"]
FALLBACK_SPEAKERS = [
    "Sayed", "Yasmin", "Mohamed", "Omar", "Ahmed", "Aly", "Hossam",
    "Kamal", "Zaki", "Essam", "Abdelrahman", "Abdullah",
    "Asmaa", "Esraa", "Hanan", "Sarah", "Omnia",
]

RTL_CSS = ".gradio-container { direction: rtl; text-align: right; }"

_ENGINE = None


# ── أدوات عامة ───────────────────────────────────────────────────────────
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


def _dropdown_update(choices: list[str], value: str | None = None):
    """تحديث قائمة منسدلة بشكل متوافق مع إصدارات Gradio."""
    import gradio as gr

    kw: dict = {"choices": choices}
    if value:
        kw["value"] = value
    upd = getattr(gr, "update", None)
    if upd is not None:
        try:
            return upd(**kw)
        except Exception:  # noqa: BLE001
            pass
    return gr.Dropdown(**kw)


# ── المحركات ─────────────────────────────────────────────────────────────
def _build_engine_from(settings: dict):
    """يبني المحرك من الإعدادات المخزّنة."""
    kind = (settings.get("engine") or "remote").lower()
    if kind == "server":
        return build_engine(
            "server",
            base_url=settings.get("server_url") or None,
            token=settings.get("token") or None,
        )
    if kind == "local":
        kwargs: dict = {"device": settings.get("device") or "cuda"}
        if settings.get("model_id"):
            kwargs["model_id"] = settings["model_id"]
        return build_engine("local", **kwargs)
    kwargs = {}
    if settings.get("server_url"):
        kwargs["base_url"] = settings["server_url"]
    if settings.get("token"):
        kwargs["hf_token"] = settings["token"]
    return build_engine("remote", **kwargs)


def get_engine():
    """المحرك الحالي (يُبنى مرة واحدة من الإعدادات المحفوظة)."""
    global _ENGINE
    if _ENGINE is None:
        settings = store.load_settings()
        try:
            _ENGINE = _build_engine_from(settings)
        except Exception:  # noqa: BLE001
            _ENGINE = build_engine("remote")
    return _ENGINE


def list_speakers() -> list[str]:
    """أسماء الأصوات الجاهزة (مع بديل ثابت لو المحرك مش جاهز)."""
    try:
        names = [s.name for s in get_engine().list_speakers()]
        return names or list(FALLBACK_SPEAKERS)
    except Exception:  # noqa: BLE001
        return list(FALLBACK_SPEAKERS)


def header_md() -> str:
    s = store.load_settings()
    return (
        f"### ⚙️ الحالي: محرك `{s.get('engine')}` · موديل `{s.get('model_id') or 'افتراضي'}`"
    )


# ── النص ─────────────────────────────────────────────────────────────────
def prepare_text(text: str, normalize: bool, diacritics: bool) -> str:
    """تطبيع النص المصري (نفس منطق الـ API) + قاموس المستخدم."""
    if not normalize:
        return text
    return normalize_for_tts(text, diacritics=diacritics, lexicon=(store.load_lexicon() or None))


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


def _as_path(obj) -> str | None:
    """يفكّ مسار الملف من قيمة Gradio (str أو File)."""
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    return getattr(obj, "name", None)


# ── التوليد والاستنساخ ───────────────────────────────────────────────────
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

    ref_path = _as_path(ref_audio)
    clean = prepare_text(text, normalize, diacritics)
    out = _out_path("clone")
    req = SynthRequest(
        text=clean, ref_audio=ref_path, ref_text=ref_text or "",
        steps=int(steps), guidance=float(guidance), speed=float(speed),
        normalize=False,
    )
    try:
        path = get_engine().clone(req, out)
    except Exception as exc:  # noqa: BLE001
        raise gr.Error(f"فشل الاستنساخ: {exc}") from exc
    return _finish(path, postprocess_on, lufs, multiband, fmt)


# ── التوليد الدفعي ───────────────────────────────────────────────────────
def batch_ui(
    files, speaker, steps, guidance, speed,
    normalize, diacritics, postprocess_on, lufs, multiband, fmt,
):
    import gradio as gr

    paths = [p for p in (_as_path(f) for f in (files or [])) if p]
    if not paths:
        raise gr.Error("ارفع ملف/ملفات نصية (.txt) الأول")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    lines: list[str] = []
    produced: list[str] = []

    for path in paths:
        name = os.path.splitext(os.path.basename(path))[0]
        spk = speaker
        if "__" in name:  # اسم__الصوت.txt → صوت مختلف لكل إعلان
            name, override = name.split("__", 1)
            spk = (override.strip() or speaker)
        try:
            with open(path, encoding="utf-8") as fh:
                raw = fh.read().strip()
            clean = prepare_text(raw, normalize, diacritics)
            out = os.path.join(OUTPUT_DIR, f"{name}.wav")
            req = SynthRequest(
                text=clean, speaker=spk, steps=int(steps),
                guidance=float(guidance), speed=float(speed), normalize=False,
            )
            p = get_engine().synthesize(req, out)
            p, info = _finish(p, postprocess_on, lufs, multiband, fmt)
            produced.append(p)
            lines.append(f"✓ {name} ({spk}) — {info}")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"✗ {name}: {exc}")

    zip_path = os.path.join(OUTPUT_DIR, f"ads_{uuid.uuid4().hex[:6]}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in produced:
            z.write(p, os.path.basename(p))

    report = "\n".join(lines) + f"\n\n**الإجمالي:** نجح {len(produced)} من {len(paths)}."
    return zip_path, report


# ── فاحص النطق ───────────────────────────────────────────────────────────
def qa_ui(audio, reference, model_size):
    import gradio as gr

    path = _as_path(audio)
    if not path:
        raise gr.Error("ارفع ملف الصوت اللي عايز تفحصه")
    if not (reference or "").strip():
        raise gr.Error("اكتب النص المتوقّع")

    try:
        from backend.qa.asr_check import check

        rep = check(path, reference, model_size or "large-v3")
    except RuntimeError as exc:
        return f"⚠️ {exc}"
    except Exception as exc:  # noqa: BLE001
        return f"⚠️ فشل الفحص: {exc}"

    out = [
        f"### نسبة التطابق: **{rep['ratio'] * 100:.1f}%**",
        "",
        f"**المتوقّع:** {rep['reference']}",
        f"**المسموع:** {rep['heard']}",
        "",
    ]
    if not rep["issues"]:
        out.append("✅ مفيش أخطاء ظاهرة")
    else:
        out.append("**الأخطاء:**")
        for it in rep["issues"]:
            extra = f" — `{it['detail']}`" if it["detail"] else ""
            out.append(f"- {it['type']}: «{it['ref']}» ← «{it['heard']}»{extra}")
    return "\n".join(out)


# ── القاموس ──────────────────────────────────────────────────────────────
def lexicon_load():
    return store.lexicon_rows()


def lexicon_save(rows):
    lex = store.rows_to_lexicon(rows)
    store.save_lexicon(lex)
    from backend.text import voicetut_norm

    voicetut_norm.reset()  # عشان الحذف/التعديل ياخد مفعوله
    return f"✅ اتحفظ القاموس ({len(lex)} كلمة) — هيُستخدم من أول التوليد الجاي.", store.lexicon_rows()


# ── الإعدادات ────────────────────────────────────────────────────────────
def apply_engine_settings(kind, server_url, token, model_id, device, speaker):
    global _ENGINE
    settings = store.load_settings()
    settings.update({
        "engine": (kind or "remote").lower(),
        "server_url": server_url or "",
        "token": token or "",
        "model_id": model_id or settings.get("model_id") or "",
        "device": device or "cuda",
    })
    store.save_settings(settings)
    try:
        _ENGINE = _build_engine_from(settings)
        speakers = [s.name for s in _ENGINE.list_speakers()] or list(FALLBACK_SPEAKERS)
        status = f"✅ اشتغل: `{getattr(_ENGINE, 'name', kind)}` — {len(speakers)} صوت متاح."
    except Exception as exc:  # noqa: BLE001
        _ENGINE = None
        speakers = list(FALLBACK_SPEAKERS)
        status = (
            f"⚠️ فشل تشغيل `{kind}`: {exc}\n\n"
            "الإعدادات اتحفظت، وهنحاول تاني أول ما تولّد (أو غيّر الإعدادات)."
        )
    value = speaker if speaker in speakers else (speakers[0] if speakers else None)
    return status, _dropdown_update(speakers, value)


def refresh_speakers(current):
    sp = list_speakers()
    value = current if current in sp else (sp[0] if sp else None)
    return _dropdown_update(sp, value), header_md()


# ── بناء الواجهة ─────────────────────────────────────────────────────────
def build_interface(speakers: list[str] | None = None):
    """يبني واجهة Gradio (يرجّع Blocks)."""
    import gradio as gr

    speakers = list(speakers) if speakers else list(FALLBACK_SPEAKERS)
    default_speaker = speakers[0] if speakers else "Sayed"
    settings = store.load_settings()

    with gr.Blocks(**_blocks_kwargs()) as demo:
        gr.Markdown(
            "# 🎙️ استوديو الصوت المصري\n"
            "مركز تحكم كامل: **توليد · استنساخ · دفعي · فحص نطق · قاموس · إعدادات**."
        )
        with gr.Row():
            speaker = gr.Dropdown(speakers, value=default_speaker, label="الصوت الجاهز", scale=4)
            refresh_btn = gr.Button("🔄 تحديث الأصوات", scale=1)
        engine_state = gr.Markdown(header_md())

        with gr.Accordion("⚙️ إعدادات عامة للصوت", open=False):
            with gr.Row():
                fmt = gr.Dropdown(["wav", "mp3"], value=str(settings.get("fmt", "wav")), label="صيغة الملف")
                multiband = gr.Dropdown(
                    MULTIBAND_CHOICES, value=str(settings.get("multiband", "") or ""),
                    label="ضغط/EQ متعدد النطاقات",
                )
                lufs = gr.Dropdown(LUFS_CHOICES, value=int(settings.get("lufs", -14)), label="جهارة الهدف (LUFS)")
            with gr.Row():
                postprocess_on = gr.Checkbox(bool(settings.get("postprocess", True)), label="معالجة صوتية احترافية")
                diacritics = gr.Checkbox(bool(settings.get("diacritics", True)), label="تشكيل / نطق أدق")
                normalize = gr.Checkbox(True, label="تطبيع النص المصري")

        with gr.Tabs():
            # ── توليد ──
            with gr.Tab("🔊 توليد"):
                text = gr.Textbox(lines=4, label="النص (عامية مصرية)")
                prev_btn = gr.Button("👁️ معاينة النطق")
                prev_txt = gr.Textbox(label="النص بعد التطبيع (زي ما الموديل هيقراه)", interactive=False)
                with gr.Row():
                    steps = gr.Slider(8, 64, value=int(settings.get("steps", 64)), step=1, label="خطوات التوليد")
                    guidance = gr.Slider(1.0, 5.0, value=float(settings.get("guidance", 2.5)), step=0.1, label="قوة التوجيه")
                    speed = gr.Slider(0.5, 2.0, value=float(settings.get("speed", 0.95)), step=0.05, label="السرعة")
                go = gr.Button("🔊 توليد", variant="primary")
                out_audio = gr.Audio(label="الناتج", type="filepath")
                out_info = gr.Textbox(label="التقرير", interactive=False)
                prev_btn.click(
                    lambda t, n, d: prepare_text(t or "", n, d),
                    [text, normalize, diacritics], [prev_txt],
                )
                go.click(
                    synth_ui,
                    [text, speaker, steps, guidance, speed,
                     normalize, diacritics, postprocess_on, lufs, multiband, fmt],
                    [out_audio, out_info],
                )

            # ── استنساخ ──
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

            # ── دفعي ──
            with gr.Tab("📦 دفعي"):
                gr.Markdown(
                    "ارفع ملفات `.txt` (كل ملف = إعلان). "
                    "سمِّ الملف `اسم__الصوت.txt` عشان تغيّر الصوت لكل إعلان."
                )
                files = gr.File(file_count="multiple", file_types=[".txt"], label="ملفات النصوص")
                go3 = gr.Button("📦 ولّد الكل", variant="primary")
                zip_out = gr.File(label="ملف مضغوط (zip)")
                batch_report = gr.Textbox(label="التقرير", lines=10, interactive=False)
                go3.click(
                    batch_ui,
                    [files, speaker, steps, guidance, speed,
                     normalize, diacritics, postprocess_on, lufs, multiband, fmt],
                    [zip_out, batch_report],
                )

            # ── فاحص النطق ──
            with gr.Tab("🔎 فاحص النطق"):
                gr.Markdown(
                    "ارفع الصوت الناتج واكتب النص المتوقّع — هنفرّغه (ASR) ونقارن **بالحرف** "
                    "عشان نكشف أي حرف ناقص/زيادة/نطق غلط."
                )
                qa_audio = gr.Audio(label="الصوت", type="filepath")
                qa_ref = gr.Textbox(lines=3, label="النص المتوقّع")
                qa_model = gr.Dropdown(
                    ASR_CHOICES, value=os.getenv("ASR_MODEL", "large-v3"), label="حجم موديل الـ ASR"
                )
                qa_btn = gr.Button("🔎 افحص", variant="primary")
                qa_out = gr.Markdown()
                qa_btn.click(qa_ui, [qa_audio, qa_ref, qa_model], [qa_out])

            # ── القاموس ──
            with gr.Tab("📖 قاموس النطق"):
                gr.Markdown(
                    "أضف كلمة/براند ونطقها: **اللاتيني** (WhatsApp) يتحوّل لعربي، "
                    "و**العربي** بياخد تشكيل أدق."
                )
                lex_df = gr.Dataframe(
                    headers=["الكلمة", "النطق"],
                    value=store.lexicon_rows(),
                    datatype=["str", "str"],
                    interactive=True,
                    label="كلمات مخصّصة",
                )
                with gr.Row():
                    lex_load_btn = gr.Button("🔄 تحميل من الملف")
                    lex_save_btn = gr.Button("💾 حفظ", variant="primary")
                lex_msg = gr.Textbox(label="الحالة", interactive=False)
                lex_load_btn.click(lexicon_load, None, [lex_df])
                lex_save_btn.click(lexicon_save, [lex_df], [lex_msg, lex_df])

            # ── الإعدادات ──
            with gr.Tab("⚙️ الإعدادات"):
                gr.Markdown(
                    "اختر **نوع المحرك**: `remote` (Space جاهز) · `server` (GPU سحابي بتاعك) · "
                    "`local` (مباشر على GPU — Colab). الإعدادات بتتحفظ تلقائيًا."
                )
                engine_kind = gr.Dropdown(
                    ENGINE_CHOICES, value=str(settings.get("engine", "remote")), label="نوع المحرك"
                )
                srv_url = gr.Textbox(value=str(settings.get("server_url", "")), label="رابط السيرفر (server / remote مخصّص)")
                srv_token = gr.Textbox(value=str(settings.get("token", "")), type="password", label="التوكن (server / HuggingFace)")
                model_id = gr.Textbox(value=str(settings.get("model_id", "")), label="معرّف الموديل (local)")
                device = gr.Dropdown(
                    ["cuda", "cpu", "mps"], value=str(settings.get("device", "cuda")), label="الجهاز (local)"
                )
                apply_btn = gr.Button("✅ تطبيق وتشغيل", variant="primary")
                eng_status = gr.Markdown()
                apply_btn.click(
                    apply_engine_settings,
                    [engine_kind, srv_url, srv_token, model_id, device, speaker],
                    [eng_status, speaker],
                )
                gr.Markdown(
                    "> 💡 من غير كارت NVIDIA محليًا: استخدم `remote` أو `server`. "
                    "للتشغيل الكامل على GPU: شغّل التطبيق على Colab واختر `local`."
                )

        refresh_btn.click(refresh_speakers, [speaker], [speaker, engine_state])

        gr.Markdown("> ⚖️ محتاج موافقة **مكتوبة** من صاحب أي صوت حقيقي قبل الاستنساخ.")

    return demo


def main() -> int:
    ap = argparse.ArgumentParser(description="واجهة Gradio للصوت المصري")
    ap.add_argument("--port", type=int, default=7860)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--share", action="store_true", help="رابط عام مؤقّت (Gradio share)")
    ap.add_argument("--engine", choices=ENGINE_CHOICES, help="يحدّد نوع المحرك ويحفظه")
    args = ap.parse_args()

    if args.engine:
        settings = store.load_settings()
        settings["engine"] = args.engine
        store.save_settings(settings)

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
