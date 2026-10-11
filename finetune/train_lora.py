"""مسار fine-tune (LoRA) لاستنساخ «نفس الأداء الصوتي» — المشغّل الفعلي.

بيشغّل مسار OmniVoice الرسمي (راجع docs/lora_finetuning.md في ريبو OmniVoice):
    المرحلة 0: تحويل التسجيلات المنظّفة لـ WebDataset shards (tokens)
    المرحلة 1: تدريب LoRA فوق الموديل المصري الأساسي (mohammedaly22/VoiceTut-TTS)
    المرحلة 2: تجميع الـ adapter في موديل كامل (merge) + عمل zips للتنزيل

الشغّل:
    # فحص الداتاسِت والخطة (من غير GPU — يشتغل محلياً)
    .venv\\Scripts\\python.exe finetune\\train_lora.py --check

    # التدريب الفعلي (على Colab / GPU — زي deploy/colab_train_voice.ipynb)
    python finetune/train_lora.py --dataset finetune/dataset --name صوت_العميل

المخرجات في finetune/runs/<name>/:
    <name>_adapter.zip   → adapter (LoRA) صغير للتحميل فوق الموديل الأساسي
    <name>_merged/       → موديل كامل مدموج (يقدر السيرفر يحمّله بـ TTS_MODEL)
    <name>_model.zip     → نسخة مضغوطة من الموديل المدموج
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DEFAULT_TOKENS_DIR = os.path.join("finetune", "runs", "tokens")
DEFAULT_CONFIG = os.path.join("finetune", "config", "train_config_finetune_lora.json")
DEFAULT_DATA_CONFIG = os.path.join("finetune", "config", "data_config_finetune.json")
DEFAULT_TOKENIZER = "eustlb/higgs-audio-v2-tokenizer"


@dataclass
class TrainConfig:
    dataset: str = os.path.join("finetune", "dataset")
    out: str = os.path.join("finetune", "runs")
    name: str = "voice"
    base_model: str = "mohammedaly22/VoiceTut-TTS"
    tokenizer: str = DEFAULT_TOKENIZER
    train_config: str = DEFAULT_CONFIG
    data_config: str = DEFAULT_DATA_CONFIG
    tokens_dir: str = DEFAULT_TOKENS_DIR
    epochs: int = 20  # للخطة/التقدير فقط — التدريب الفعلي بالخطوات من train_config
    batch_size: int = 4
    grad_accum: int = 2
    lr: float = 1e-4
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    max_sec: float = 20.0
    seed: int = 42
    merge: bool = True
    extras: dict = field(default_factory=dict)


# ── قراءة الداتاسِت ─────────────────────────────────────────────────────

def load_manifest(path: str) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def check_dataset(dataset_dir: str) -> dict:
    """يتأكد إن الداتاسِت سليم ويرجّع تقرير (مالوش علاقة بـ GPU)."""
    train_p = os.path.join(dataset_dir, "train.jsonl")
    val_p = os.path.join(dataset_dir, "val.jsonl")
    if not os.path.exists(train_p) or not os.path.exists(val_p):
        raise FileNotFoundError(f"الداتاسِت ناقص: محتاج {train_p} و {val_p}")

    def count(p: str) -> int:
        return sum(1 for line in open(p, encoding="utf-8") if line.strip())

    clips_dir = os.path.join(dataset_dir, "clips")
    n_train, n_val = count(train_p), count(val_p)
    if n_train + n_val == 0:
        raise ValueError("الداتاسِت فاضي")
    return {
        "train": n_train,
        "val": n_val,
        "total": n_train + n_val,
        "clips_ok": os.path.isdir(clips_dir) and bool(os.listdir(clips_dir)),
        "dataset_dir": dataset_dir,
    }


def plan(cfg: TrainConfig, rep: dict) -> dict:
    """خطة تدريب تقريبية (بيانات متاحة قبل الشغل)."""
    per_step = max(cfg.batch_size * cfg.grad_accum, 1)
    steps_per_epoch = max(int(rep["train"] / per_step + 0.999), 1)
    total_steps = steps_per_epoch * cfg.epochs
    # تقدير: ~0.1 ثانية لكل عيّنة لكل خطوة على T4 مع LoRA صغير
    total_minutes = round(total_steps * 0.25 / 60.0, 2)
    return {
        "steps_per_epoch": steps_per_epoch,
        "total_steps": total_steps,
        "total_minutes": total_minutes,
        "lr": cfg.lr,
        "lora_rank": cfg.lora_rank,
    }


# ── المرحلة 0: تحويل الداتاسِت لصيغة OmniVoice + tokenize ───────────────

def write_manifests(dataset_dir: str, out_dir: str, language_id: str = "arz") -> dict:
    """يحوّل our train/val.jsonl لـ manifests بصيغة OmniVoice.

    الدخل (من finetune/prepare_dataset.py):
        {audio: "clips/x.wav", text: "..."}
    المخرج (صيغة run_finetune_lora.sh الرسمية):
        {id, audio_path (مطلق), text, language_id}
    """
    clips_dir = os.path.join(dataset_dir, "clips")
    os.makedirs(out_dir, exist_ok=True)
    counts: dict[str, int] = {}

    for split in ("train", "dev"):
        src_p = os.path.join(dataset_dir, "train.jsonl" if split == "train" else "val.jsonl")
        src = load_manifest(src_p)
        out_rows: list[dict] = []
        seen: set[str] = set()
        for i, row in enumerate(src):
            stem = os.path.splitext(os.path.basename(str(row.get("audio", f"clip_{i}"))))[0]
            base = f"{stem}_{i}" if stem in seen else stem
            seen.add(stem)
            audio_path = os.path.join(dataset_dir, str(row["audio"]))
            out_rows.append({
                "id": base,
                "audio_path": os.path.abspath(audio_path),
                "text": str(row.get("text", "")),
                "language_id": language_id,
            })
        out_p = os.path.join(out_dir, f"{split}.jsonl")
        with open(out_p, "w", encoding="utf-8") as fh:
            for row in out_rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        counts[split] = len(out_rows)
    return counts


def _run(cmd: list[str], step_label: str) -> None:
    print(f"\n[🔧 {step_label}]")
    print("    " + " ".join(str(c) for c in cmd[:3]) + " …" if len(cmd) > 3 else "    " + " ".join(cmd))
    try:
        subprocess.run(cmd, cwd=ROOT, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"فشل {step_label} (كود {exc.returncode})") from exc


def run_stage0(cfg: TrainConfig) -> None:
    """tokenize الـ manifests → WebDataset shards."""
    os.makedirs(cfg.tokens_dir, exist_ok=True)
    for split, src in (("train", "train.jsonl"), ("dev", "val.jsonl")):
        manifest = os.path.join(_write_man_dir(cfg), src)
        _run([
            sys.executable, "-m", "omnivoice.scripts.extract_audio_tokens",
            "--input_jsonl", manifest,
            "--tar_output_pattern",
            os.path.join(cfg.tokens_dir, split, "audios", "shard-%06d.tar"),
            "--jsonl_output_pattern",
            os.path.join(cfg.tokens_dir, split, "txts", "shard-%06d.jsonl"),
            "--tokenizer_path", cfg.tokenizer,
        ], f"transcribe: {split}")


def _write_man_dir(cfg: TrainConfig) -> str:
    """مجلد الـ manifests المحوّلة (جنب الـ tokens)."""
    man_dir = os.path.join(os.path.dirname(cfg.tokens_dir), "manifests")
    if not os.path.exists(os.path.join(man_dir, "train.jsonl")):
        os.makedirs(man_dir, exist_ok=True)
        write_manifests(cfg.dataset, man_dir)
    return man_dir


# ── المرحلة 1: التدريب ───────────────────────────────────────────────────

def run_stage1(cfg: TrainConfig) -> str:
    """تشغيل accelerate + omnivoice.cli.train (LoRA حسب train_config)."""
    _run([
        sys.executable, "-m", "accelerate", "launch",
        "--num_processes", "1",
        "-m", "omnivoice.cli.train",
        "--train_config", cfg.train_config,
        "--data_config", cfg.data_config,
        "--output_dir", os.path.join(cfg.out, cfg.name),
    ], "تدريب LoRA على GPU")

    ckpt = find_latest_checkpoint(os.path.join(cfg.out, cfg.name))
    if not ckpt:
        raise RuntimeError("التدريب خلص بس مفيش checkpoint — راجع اللوج")
    return ckpt


def find_latest_checkpoint(out_dir: str) -> str | None:
    best: str | None = None
    best_step = -1
    if os.path.isdir(out_dir):
        for entry in os.listdir(out_dir):
            if not entry.startswith("checkpoint-"):
                continue
            try:
                step = int(entry.split("-")[-1])
            except ValueError:
                continue
            if step > best_step:
                best_step = step
                best = os.path.join(out_dir, entry)
    return best


# ── المرحلة 2: التجميع + التغليف ─────────────────────────────────────────

def merge_adapter(cfg: TrainConfig, ckpt: str) -> str:
    """دمج الـ LoRA في الموديل الأساسي → موديل كامل (من غير PEFT جوه)."""
    merged = os.path.join(cfg.out, cfg.name, "merged")
    _run([
        "omnivoice-merge-lora",
        "--base_model", cfg.base_model,
        "--lora_adapter", ckpt,
        "--output_dir", merged,
    ], "دمج الـ adapter في موديل كامل")
    return merged


def _zip_dir(paths: list[str], zip_path: str) -> None:
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            if os.path.isfile(p):
                z.write(p, os.path.basename(p))


def package_voice(cfg: TrainConfig, ckpt: str) -> dict:
    """يغلّف الـ adapter (زومبي صغير) + الموديل المدموج (كامل) + بطاقة الصوت."""
    os.makedirs(cfg.out, exist_ok=True)
    adapter_zip = os.path.join(cfg.out, cfg.name, f"{cfg.name}_adapter.zip")
    adapter_files = [
        os.path.join(ckpt, "adapter_config.json"),
        os.path.join(ckpt, "adapter_model.safetensors"),
        os.path.join(ckpt, "tokenizer.json"),
        os.path.join(ckpt, "tokenizer_config.json"),
    ]
    _zip_dir([p for p in adapter_files if os.path.isfile(p)], adapter_zip)

    model_zip = ""
    merged = ""
    if cfg.merge:
        merged = merge_adapter(cfg, ckpt)
        model_zip = os.path.join(cfg.out, cfg.name, f"{cfg.name}_model.zip")
        _zip_dir(
            [os.path.join(merged, n) for n in os.listdir(merged)],
            model_zip,
        )

    card = {
        "name": cfg.name,
        "base_model": cfg.base_model,
        "adapter_zip": os.path.relpath(adapter_zip, ROOT),
        "merged_dir": os.path.relpath(merged, ROOT) if merged else "",
        "model_zip": os.path.relpath(model_zip, ROOT) if model_zip else "",
        "lora_rank": cfg.lora_rank,
        "lora_alpha": cfg.lora_alpha,
        "lr": cfg.lr,
        "trained_at": time.strftime("%Y-%m-%d %H:%M"),
    }
    with open(os.path.join(cfg.out, cfg.name, f"{cfg.name}.json"), "w", encoding="utf-8") as fh:
        json.dump(card, fh, ensure_ascii=False, indent=2)
    return card


# ── الواجهة ───────────────────────────────────────────────────────────────

def build_config(args: argparse.Namespace) -> TrainConfig:
    return TrainConfig(
        dataset=args.dataset,
        out=args.out,
        name=args.name,
        base_model=args.base_model,
        tokenizer=args.tokenizer,
        train_config=args.train_config,
        data_config=args.data_config,
        tokens_dir=args.tokens_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        grad_accum=args.grad_accum,
        lr=args.lr,
        lora_rank=args.lora_rank,
        merge=not args.skip_merge,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="تدريب صوت العميل (LoRA فوق VoiceTut-TTS)")
    ap.add_argument("--dataset", default=TrainConfig.dataset, help="مخرج finetune/prepare_dataset.py")
    ap.add_argument("--out", default=TrainConfig.out)
    ap.add_argument("--name", default="voice", help="اسم صوت العميل (بيدخل في أسماء الملفات)")
    ap.add_argument("--base-model", default=TrainConfig.base_model)
    ap.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    ap.add_argument("--train-config", default=DEFAULT_CONFIG)
    ap.add_argument("--data-config", default=DEFAULT_DATA_CONFIG)
    ap.add_argument("--tokens-dir", default=DEFAULT_TOKENS_DIR)
    ap.add_argument("--epochs", type=int, default=20, help="للخطة/التقدير بس")
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--grad-accum", type=int, default=2)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--lora-rank", type=int, default=16)
    ap.add_argument("--check", action="store_true", help="فحص الداتاسِت + خطة تدريب (من غير GPU)")
    ap.add_argument("--skip-merge", action="store_true", help="متدمجش الموديل (adapter بس)")
    args = ap.parse_args()

    cfg = build_config(args)

    if args.check:
        rep = check_dataset(cfg.dataset)
        info = plan(cfg, rep)
        print("[✓] الداتاسِت سليم:")
        print(f"    تدريب: {rep['train']} | تحقق: {rep['val']} | مقاطع جاهزة: {rep['clips_ok']}")
        print("[🧭] خطة التدريب التقريبية:")
        print(f"    خطوات/epoch: {info['steps_per_epoch']} | الإجمالي: {info['total_steps']}")
        print(f"    تقدير المدة على T4: ~{info['total_minutes']} دقيقة")
        print(f"    LR: {info['lr']} | LoRA rank: {info['lora_rank']}")
        print("    موديل الأساس: " + cfg.base_model)
        print("    train_config: " + cfg.train_config)
        return 0

    rep = check_dataset(cfg.dataset)
    print(f"[✓] الداتاسِت: {rep['train']} تدريب + {rep['val']} تحقق")

    run_stage0(cfg)
    ckpt = run_stage1(cfg)
    print("[✓] اتدرب: " + ckpt)

    card = package_voice(cfg, ckpt)
    print("[✓] صوت العميل جاهز:")
    for k, v in card.items():
        print(f"    {k}: {v}")
    print("\n🔽 استخدم الموديل المدموج مع السيرفر (TTS_MODEL) أو ارفع الـ zips على الجهاز.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())