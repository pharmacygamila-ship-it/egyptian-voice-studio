"""اختبار واجهة Gradio (يُتخطّى لو gradio مش مثبّت).

    .venv\\Scripts\\python.exe tests\\test_gradio.py
"""
from __future__ import annotations

import os
import sys
import tempfile

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

try:
    import gradio  # noqa: F401

    HAS_GRADIO = True
except ImportError:
    HAS_GRADIO = False

if not HAS_GRADIO:
    print("[SKIP] gradio مش مثبّت — تخطّي اختبار الواجهة")
    raise SystemExit(0)

from frontend import app_gradio as app  # noqa: E402

ok = True
total = 0


def check(label: str, cond: bool) -> None:
    global ok, total
    total += 1
    ok = ok and cond
    print(f"[{'PASS' if cond else 'FAIL'}] {label}")


class _Speaker:
    def __init__(self, name: str) -> None:
        self.name = name


def tone(sr: int, seconds: float = 1.0) -> np.ndarray:
    t = np.arange(int(sr * seconds)) / sr
    return (0.3 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)


class FakeEngine:
    """محرك وهمي بيكتب نغمة بدل ما ينادي الشبكة."""

    name = "fake"

    def list_speakers(self):
        return [_Speaker("Sayed"), _Speaker("Yasmin")]

    def synthesize(self, req, out):
        sf.write(out, tone(24000), 24000)
        return out

    def clone(self, req, out):
        sf.write(out, tone(24000), 24000)
        return out


tmp = tempfile.mkdtemp(prefix="tts_gradio_")
os.environ["TTS_OUTPUT_DIR"] = tmp

# ── 1) helpers نقية ──────────────────────────────────────────────────────
check("prepare_text: تطبيع", app.prepare_text("خصم 50", True, False) == "خصم خمسين")
check("prepare_text: بدون تطبيع", app.prepare_text("خصم 50", False, False) == "خصم 50")
check("prepare_text: تشكيل", app.prepare_text("عرض خاص", True, True) == "عَرْض خاص")
check("MULTIBAND_CHOICES", set(app.MULTIBAND_CHOICES) == {"", "voice", "warm", "punch", "broadcast"})
check("FALLBACK_SPEAKERS غير فاضي", len(app.FALLBACK_SPEAKERS) >= 10)
check("_blocks_kwargs يرجّع dict", isinstance(app._blocks_kwargs(), dict))
check("_launch_kwargs يرجّع dict", isinstance(app._launch_kwargs(), dict))

# ── 2) بناء الواجهة ──────────────────────────────────────────────────────
demo = app.build_interface(speakers=["Sayed", "Yasmin"])
check("build_interface: Blocks", isinstance(demo, gradio.Blocks))
check("build_interface: فيه مكونات", len(demo.blocks) > 10)
print(f"    -> عدد المكونات: {len(demo.blocks)}")

# ── 3) التوليد من غير شبكة (محرك وهمي) ───────────────────────────────────
app._ENGINE = FakeEngine()

path, info = app.synth_ui(
    "جرب قهوة النهاردة", "Sayed", 64, 2.5, 0.95, True, False, True, -14, "voice", "mp3"
)
check("synth_ui: mp3 اتكتب", path.endswith(".mp3") and os.path.exists(path))
check("synth_ui: التقرير فيه LUFS", "LUFS" in info)
print(f"    -> {os.path.basename(path)} | {info}")

ref = os.path.join(tmp, "ref.wav")
sf.write(ref, tone(24000, 2.0), 24000)
path2, info2 = app.clone_ui(
    ref, "نص المرجع", "النص الجديد", 32, 2.5, 1.0, True, False, True, -16, "", "wav"
)
check("clone_ui: wav اتكتب", path2.endswith(".wav") and os.path.exists(path2))
check("clone_ui: التقرير فيه LUFS", "LUFS" in info2)

# ── 4) التحقق من المدخلات ────────────────────────────────────────────────
try:
    app.synth_ui("  ", "Sayed", 64, 2.5, 0.95, True, False, True, -14, "", "wav")
    check("synth_ui: يرفض النص الفاضي", False)
except Exception:  # noqa: BLE001
    check("synth_ui: يرفض النص الفاضي", True)

try:
    app.clone_ui(None, "", "نص", 64, 2.5, 0.95, True, False, True, -14, "", "wav")
    check("clone_ui: يرفض بدون مرجع", False)
except Exception:  # noqa: BLE001
    check("clone_ui: يرفض بدون مرجع", True)

# ── 5) list_speakers من المحرك ───────────────────────────────────────────
check("list_speakers: من المحرك", app.list_speakers() == ["Sayed", "Yasmin"])

print(f"\n==> {total} اختبار |", "كله تمام ✅" if ok else "فيه فشل ❌")
raise SystemExit(0 if ok else 1)
