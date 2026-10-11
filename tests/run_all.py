"""يشغّل كل اختبارات المشروع مرة واحدة.

    .venv\\Scripts\\python.exe tests\\run_all.py
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = [
    "selfcheck.py",
    "test_text.py",
    "test_audio.py",
    "test_finetune.py",
    "check_http.py",
]

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

env = os.environ.copy()
env["PYTHONUTF8"] = "1"

results: list[tuple[str, bool]] = []
for name in TESTS:
    path = os.path.join(ROOT, "tests", name)
    print(f"\n{'=' * 50}\n▶ {name}\n{'=' * 50}")
    proc = subprocess.run([sys.executable, path], cwd=ROOT, env=env)
    results.append((name, proc.returncode == 0))

print(f"\n{'=' * 50}\n📊 الملخّص\n{'=' * 50}")
for name, passed in results:
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
all_ok = all(p for _, p in results)
print("\n==>", "كل الاختبارات ناجحة ✅" if all_ok else "فيه فشل ❌")
raise SystemExit(0 if all_ok else 1)
