"""يبني ملف مضغوط جاهز للرفع على Google Colab.

    .venv\\Scripts\\python.exe deploy\\make_bundle.py
ينتج:  dist/colab_bundle.zip
"""
from __future__ import annotations

import glob
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "dist", "colab_bundle.zip")

README = """# حزمة Colab — استوديو الصوت المصري

## الخطوات
1. افتح https://colab.research.google.com
2. `File` → `Upload notebook` → ارفع `colab_free_gpu.ipynb`
3. من القائمة: `Runtime` → `Change runtime type` → **T4 GPU** → `Save`
4. شغّل الخلايا بالترتيب (Shift + Enter)
5. عدّل نصوص الإعلانات من مجلد `scripts/` (انسخ محتواها داخل الخلية رقم 4)
6. في الآخر هيتنزّلك ملف `ads.zip` فيه كل الأصوات

## الملفات
- `colab_free_gpu.ipynb` — الـ notebook الجاهز
- `scripts/` — نصوص إعلانات جاهزة (عامية مصرية)
- `README_Colab.md` — الملف ده

## ملاحظات
- الموديل: VoiceTut-TTS (مصري، Apache-2.0، تجاري مسموح).
- لازم تشغّل على GPU (T4) وإلا هيكون بطيء جداً.
- Colab مجاني **للتوليد** بس — مش سيرفر دائم (استخدم Modal/RunPod لو عايز API شغّال 24 ساعة).
- استخدم الأصوات بموافقة أصحابها، وممنوع الانتحال أو التضليل.
"""


def main() -> int:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    notebook = os.path.join(ROOT, "deploy", "colab_free_gpu.ipynb")
    scripts = sorted(glob.glob(os.path.join(ROOT, "data", "scripts", "*.txt")))

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(notebook, "colab_free_gpu.ipynb")
        for path in scripts:
            z.write(path, "scripts/" + os.path.basename(path))
        z.writestr("README_Colab.md", README)

    size = os.path.getsize(OUT)
    print(f"[✓] {OUT}  ({size:,} bytes)")
    print(f"    notebook: 1 | نصوص: {len(scripts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
