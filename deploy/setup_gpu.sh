#!/usr/bin/env bash
# تجهيز بيئة GPU من الصفر (RunPod / Vast.ai / أي سيرفر فيه NVIDIA).
# الاستخدام:  bash deploy/setup_gpu.sh
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[1/4] تثبيت متطلبات النظام..."
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y --no-install-recommends git ffmpeg libsndfile1
fi

echo "[2/4] تحقّق من كارت الشاشة..."
nvidia-smi || echo "⚠️  مفيش nvidia-smi — تأكد إنك على جهاز فيه GPU."

echo "[3/4] تثبيت مكتبات بايثون..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements-gpu.txt

echo "[4/4] تحقّق من PyTorch + CUDA..."
python3 - <<'PY'
import torch
print("torch:", torch.__version__)
print("cuda available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0))
PY

echo "✅ التجهيز خلص. شغّل السيرفر بـ:  bash deploy/run_server.sh"
