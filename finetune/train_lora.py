"""مسار fine-tune (LoRA) لاستنساخ «نفس الأداء الصوتي».

⚠️ أمانة تقنية:
    الـ API الرسمي **للتدريب** في OmniVoice/VoiceTut مش ثابت (بيتغيّر بين
    الإصدارات). عشان كده السكربت ده:

    ✅ شغّال ومختبر: قراءة الداتاسِت + التحقق + حساب خطوات التدريب (--check).
    🔌 نقطة تركيب واحدة: `build_trainer()` — توصّل فيها الـ trainer الرسمي
       حسب نسخة OmniVoice عندك (راجع finetune/README.md).

الأوامر:
    # فحص الداتاسِت والإعدادات (من غير GPU — يشتغل محلياً)
    .venv\\Scripts\\python.exe finetune\\train_lora.py --check

    # التدريب الفعلي (محتاج GPU)
    python finetune/train_lora.py --dataset finetune/dataset --epochs 20
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class TrainConfig:
    dataset: str = "finetune/dataset"
    out: str = "finetune/runs/voice"
    base_model: str = "mohammedaly22/VoiceTut-TTS"
    epochs: int = 20
    batch_size: int = 4
    grad_accum: int = 2
    lr: float = 1e-4
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    max_sec: float = 20.0
    seed: int = 42
    extras: dict = field(default_factory=dict)


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
    for path in (train_p, val_p):
        if not os.path.exists(path):
            raise FileNotFoundError(f"مفيش {path} — شغّل finetune/prepare_dataset.py الأول")

    report = {"train": 0, "val": 0, "total_seconds": 0.0, "missing": [], "empty_text": []}
    for label, path in (("train", train_p), ("val", val_p)):
        for row in load_manifest(path):
            audio = os.path.join(dataset_dir, row.get("audio", ""))
            if not os.path.exists(audio):
                report["missing"].append(audio)
                continue
            if not str(row.get("text", "")).strip():
                report["empty_text"].append(audio)
                continue
            report[label] += 1
            report["total_seconds"] += float(row.get("duration", 0.0))

    if report["train"] == 0:
        raise ValueError("مفيش بيانات تدريب صالحة")
    return report


def plan(cfg: TrainConfig, report: dict) -> dict:
    """يحسب خطة التدريب (خطوات/وقت تقديري)."""
    steps_per_epoch = max(1, report["train"] // (cfg.batch_size * cfg.grad_accum))
    total_steps = steps_per_epoch * cfg.epochs
    return {
        "train_clips": report["train"],
        "val_clips": report["val"],
        "total_minutes": round(report["total_seconds"] / 60.0, 1),
        "steps_per_epoch": steps_per_epoch,
        "total_steps": total_steps,
        "epochs": cfg.epochs,
        "batch_size": cfg.batch_size,
        "grad_accum": cfg.grad_accum,
        "lr": cfg.lr,
        "lora_rank": cfg.lora_rank,
    }


def build_trainer(cfg: TrainConfig):  # pragma: no cover - يعتمد على GPU
    """🔌 نقطة التركيب — توصّل فيها الـ trainer الرسمي لـ OmniVoice/VoiceTut.

    الخطوات العامة (راجع finetune/README.md):
        1) حمّل الموديل الأساسي: cfg.base_model
        2) لُفّ الـ decoder بـ LoRA (rank=cfg.lora_rank, alpha=cfg.lora_alpha)
        3) جهّز DataLoader من train.jsonl/val.jsonl (audio 24kHz + text)
        4) استخدم loss = CTC أو flow-matching حسب الموديل
        5) رجّع كائن فيه `.train()`
    """
    raise NotImplementedError(
        "لازم تركّب API التدريب الرسمي لـ OmniVoice هنا (شوف finetune/README.md)."
    )


def train(cfg: TrainConfig) -> None:  # pragma: no cover - يعتمد على GPU
    report = check_dataset(cfg.dataset)
    info = plan(cfg, report)
    print("[i] خطة التدريب:", json.dumps(info, ensure_ascii=False))
    try:
        import torch  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "مفيش Torch/GPU محلياً — شغّل التدريب على GPU (Colab/RunPod/Modal). "
            "راجع finetune/README.md"
        ) from exc
    os.makedirs(cfg.out, exist_ok=True)
    trainer = build_trainer(cfg)
    trainer.train()
    print(f"[✓] خلص التدريب → {cfg.out}")


def main() -> int:
    ap = argparse.ArgumentParser(description="fine-tune (LoRA) لصوت العميل")
    ap.add_argument("--dataset", default="finetune/dataset")
    ap.add_argument("--out", default="finetune/runs/voice")
    ap.add_argument("--base-model", default="mohammedaly22/VoiceTut-TTS")
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--grad-accum", type=int, default=2)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--lora-rank", type=int, default=16)
    ap.add_argument("--check", action="store_true", help="فحص الداتاسِت من غير تدريب")
    args = ap.parse_args()

    cfg = TrainConfig(
        dataset=args.dataset, out=args.out, base_model=args.base_model,
        epochs=args.epochs, batch_size=args.batch_size, grad_accum=args.grad_accum,
        lr=args.lr, lora_rank=args.lora_rank,
    )

    if args.check:
        report = check_dataset(cfg.dataset)
        info = plan(cfg, report)
        print("[✓] الداتاسِت سليم:")
        print(f"    تدريب: {report['train']} | تحقق: {report['val']} | "
              f"إجمالي {info['total_minutes']} دقيقة")
        print(f"    {info['epochs']} epochs × {info['steps_per_epoch']} خطوة = "
              f"{info['total_steps']} خطوة | lr={info['lr']} | LoRA r={info['lora_rank']}")
        if report["missing"]:
            print(f"    ⚠️ {len(report['missing'])} ملف ناقص")
        return 0

    train(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
