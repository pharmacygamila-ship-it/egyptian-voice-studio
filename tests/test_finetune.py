"""اختبار تجهيز داتاسِت fine-tune.

    .venv\\Scripts\\python.exe tests\\test_finetune.py
"""
from __future__ import annotations

import json
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

from finetune.prepare_dataset import collect, load_transcripts, prepare  # noqa: E402

ok = True
total = 0


def check(label: str, cond: bool) -> None:
    global ok, total
    total += 1
    ok = ok and cond
    print(f"[{'PASS' if cond else 'FAIL'}] {label}")


def tone(sr: int, seconds: float, freq: float = 220.0) -> np.ndarray:
    pad = int(sr * 0.3)
    t = np.arange(int(sr * seconds)) / sr
    core = 0.3 * np.sin(2 * np.pi * freq * t)
    return np.concatenate([np.zeros(pad), core, np.zeros(pad)])


tmp = tempfile.mkdtemp(prefix="tts_ft_")
src = os.path.join(tmp, "voice")
os.makedirs(src)

# مقاطع صالحة + نصها
sr0 = 16000  # مصدر مختلف الترددات عشان نتأكد من إعادة التنميط
valid = {"clip01": 4.0, "clip02": 6.0, "clip03": 3.0}
for name, secs in valid.items():
    sf.write(os.path.join(src, f"{name}.wav"), tone(sr0, secs), sr0)

# مقاطع مرفوضة
sf.write(os.path.join(src, "short.wav"), tone(sr0, 0.8), sr0)   # قصير
sf.write(os.path.join(src, "long.wav"), tone(sr0, 25.0), sr0)   # طويل
sf.write(os.path.join(src, "notext.wav"), tone(sr0, 4.0), sr0)  # من غير نص

# ملف النصوص
transcripts = os.path.join(src, "transcripts.txt")
with open(transcripts, "w", encoding="utf-8") as fh:
    for name in valid:
        fh.write(f"{name}.wav|جملة تجريبية للتسجيل رقم {name}\n")
    fh.write("short.wav|قصير جدا\n")
    fh.write("long.wav|طويل جدا\n")

# ── قراءة النصوص ─────────────────────────────────────────────────────────
table = load_transcripts(transcripts)
check("load_transcripts: 5 مدخلات", len(table) == 5)
check("load_transcripts: النص صح", table["clip01"].startswith("جملة تجريبية"))

# ── الجمع ────────────────────────────────────────────────────────────────
items = collect(src, transcripts)
check("collect: 6 ملفات صوت", len(items) == 6)
check("collect: notext من غير نص", any(p.endswith("notext.wav") and not t for p, t in items))

# ── التجهيز الكامل ───────────────────────────────────────────────────────
out = os.path.join(tmp, "dataset")
report = prepare(src, out, transcripts, min_sec=2.0, max_sec=20.0, target_sr=24000)

check("prepare: 3 مقاطع مقبولة", report["kept"] == 3)
check("prepare: 3 مرفوضة", report["dropped"] == 3)
check("prepare: train + val = 3", report["train"] + report["val"] == 3)
check("prepare: SR = 24000", report["target_sr"] == 24000)

clips = os.listdir(os.path.join(out, "clips"))
check("prepare: ملفات المقاطع اتكتبت", len(clips) == 3)

# المقاطع كلها 24kHz أحادية
all_ok = True
for c in clips:
    d, s = sf.read(os.path.join(out, "clips", c))
    all_ok = all_ok and s == 24000 and d.ndim == 1
check("prepare: كل المقاطع 24kHz أحادية", all_ok)

# jsonl صالح
with open(os.path.join(out, "train.jsonl"), encoding="utf-8") as fh:
    rows = [json.loads(line) for line in fh if line.strip()]
check("prepare: train.jsonl صالح", len(rows) >= 1 and "audio" in rows[0] and "text" in rows[0])

# التقرير موجود
check("prepare: report.json اتكتب", os.path.exists(os.path.join(out, "report.json")))

# ── رفض داتاسِت فاضي ─────────────────────────────────────────────────────
empty = os.path.join(tmp, "empty")
os.makedirs(empty)
try:
    prepare(empty, os.path.join(tmp, "out2"))
    check("prepare: يرفض مجلد فاضي", False)
except ValueError:
    check("prepare: يرفض مجلد فاضي", True)

# ── فحص الداتاسِت + خطة التدريب ──────────────────────────────────────────
from finetune.train_lora import TrainConfig, check_dataset, plan  # noqa: E402

rep = check_dataset(out)
check("check_dataset: تدريب+تحقق = 3", rep["train"] + rep["val"] == 3)
cfg = TrainConfig(dataset=out, epochs=10, batch_size=2, grad_accum=1)
info = plan(cfg, rep)
check("plan: خطوات = خطوات/epoch × epochs", info["total_steps"] == info["steps_per_epoch"] * 10)
check("plan: دقايق موجبة", info["total_minutes"] > 0)
try:
    check_dataset(os.path.join(tmp, "nope"))
    check("check_dataset: يرفض داتاسِت ناقص", False)
except FileNotFoundError:
    check("check_dataset: يرفض داتاسِت ناقص", True)

# ── المرحلة 0: تحويل الـ manifests بصيغة OmniVoice ───────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from finetune.train_lora import write_manifests  # noqa: E402

man_dir = os.path.join(tmp, "manifests")
counts = write_manifests(out, man_dir)
check("write_manifests: train + dev = 3", counts["train"] + counts["dev"] == 3)

_train_rows = [
    json.loads(l) for l in open(os.path.join(man_dir, "train.jsonl"), encoding="utf-8") if l.strip()
]
_dev_rows = [
    json.loads(l) for l in open(os.path.join(man_dir, "dev.jsonl"), encoding="utf-8") if l.strip()
]
_all = _train_rows + _dev_rows
check(
    "write_manifests: الحقول كاملة",
    all({"id", "audio_path", "text", "language_id"} <= set(r) for r in _all),
)
check("write_manifests: مسارات مطلقة وموجودة", all(os.path.isfile(r["audio_path"]) for r in _all))
check("write_manifests: لغة arz", all(r["language_id"] == "arz" for r in _all))
check("write_manifests: نصوص غير فاضية", all(str(r["text"]).strip() for r in _all))

# ── configs التدريب الرسمية ──────────────────────────────────────────────
tr_cfg = json.load(open(os.path.join(ROOT, "finetune", "config", "train_config_finetune_lora.json")))
check("train_config: use_lora", tr_cfg.get("use_lora") is True)
check("train_config: أساسه VoiceTut المصري",
      tr_cfg.get("init_from_checkpoint") == "mohammedaly22/VoiceTut-TTS")
check("train_config: lora_target_modules متاح", len(tr_cfg.get("lora_target_modules", [])) > 0)

dt_cfg = json.load(open(os.path.join(ROOT, "finetune", "config", "data_config_finetune.json")))
check("data_config: train lst موجود",
      "finetune/runs/tokens/train/data.lst" in str(dt_cfg.get("train")))
check("data_config: dev lst موجود",
      "finetune/runs/tokens/dev/data.lst" in str(dt_cfg.get("dev")))

# ── train_lora --check (من غير GPU) ──────────────────────────────────────
import subprocess  # noqa: E402

env = os.environ.copy()
env["PYTHONUTF8"] = "1"
proc = subprocess.run(
    [sys.executable, "finetune/train_lora.py", "--check", "--dataset", out],
    cwd=ROOT, env=env, capture_output=True, text=True,
)
check("train_lora --check: يخرج 0", proc.returncode == 0)
check("train_lora --check: الخطة في المخرج", "خطة التدريب" in proc.stdout)

print(f"\n==> {total} اختبار |", "كله تمام ✅" if ok else "فيه فشل ❌")
raise SystemExit(0 if ok else 1)
