# 🎙️ تطبيق استنساخ الصوت — عامية مصرية

تطبيق لإنتاج تعليق صوتي (Voice Over) للإعلانات بالعامية المصرية، مع استنساخ
صوت العميل — مبني على **[VoiceTut-TTS](https://huggingface.co/mohammedaly22/VoiceTut-TTS)**
(مصري أصلي + code-switching عربي↔إنجليزي + 17 صوت + استنساخ، رخصة Apache-2.0 → تجاري مسموح).

> التفاصيل الكاملة والخطة في [`PLAN.md`](PLAN.md).

---

## ⚡ الحالة الحالية

- ✅ الجهاز: تم تثبيت **Python 3.12** + بيئة افتراضية `.venv`.
- ✅ محرك أونلاين شغّال (`RemoteVoiceTutEngine`) → يولّد صوت فوراً **من غير GPU**.
- ✅ معمارية **عميل/سيرفر** جاهزة للـ GPU السحابي (`ServerVoiceTutEngine` + `deploy/`).
- ✅ نموذج صوت جاهز: `data/outputs/ads_sample_01_Sayed.wav`
- ✅ كل الاختبارات ناجحة: `tests/selfcheck.py` و `tests/check_http.py`
- ⚠️ كارت الشاشة الحالي (AMD 2GB) مش بينفع → للإنتاج نشغّل على **GPU سحابي** (شوف `deploy/README.md`).

---

## 🗂️ بنية المشروع

```
اعلانات 2/
├─ PLAN.md                     الخطة الكاملة
├─ README.md                   الدليل ده
├─ Dockerfile                  صورة GPU جاهزة
├─ requirements.txt            مكتبات محلية (خفيفة)
├─ requirements-gpu.txt        مكتبات GPU
├─ poc_generate.py             سطر أوامر للتوليد السريع
├─ .env.example                مثال إعدادات
├─ backend/
│   ├─ main.py                 FastAPI (/health /voices /tts /clone) + حماية توكن
│   ├─ engine/
│   │   ├─ base.py             الواجهة المشتركة
│   │   ├─ remote_voicetut.py  محرك أونلاين (الـ Space)
│   │   ├─ server_client.py    عميل سيرفر GPU بتاعنا
│   │   └─ local_voicetut.py   محرك محلي/GPU
│   ├─ text/normalize.py       تطبيع النص المصري
│   └─ audio/postprocess.py    معالجة صوت إعلانية
├─ deploy/
│   ├─ README.md               خطوات RunPod / Vast.ai / Docker
│   ├─ setup_gpu.sh            تجهيز بيئة GPU
│   ├─ run_server.sh           تشغيل السيرفر
│   └─ docker-compose.yml
├─ tests/
│   ├─ selfcheck.py            فحص المكونات
│   └─ check_http.py           فحص السيرفر والعميل
└─ data/
    ├─ scripts/                نصوص الإعلانات
    └─ outputs/                الأصوات المُولّدة
```

---

## 🚀 التشغيل

### 1) توليد سريع (سطر أوامر)
```powershell
.\.venv\Scripts\python.exe poc_generate.py --speaker Sayed --text "أهلاً بيك في تطبيقنا الجديد"
```
أو من ملف نصي:
```powershell
.\.venv\Scripts\python.exe poc_generate.py --speaker Yasmin --text-file data\scripts\ad1.txt --out data\outputs\ad1.wav
```
استنساخ صوت من مقطع مرجعي:
```powershell
.\.venv\Scripts\python.exe poc_generate.py --ref-audio my_voice.wav --ref-text "النص المرجعي" --text "كلام جديد بالعامية"
```

### 2) سيرفر الـ API
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
```
- `GET  /health`  → حالة المحرك
- `GET  /voices`  → الأصوات الجاهزة
- `POST /tts`     → JSON: `{ "text": "...", "speaker": "Sayed" }`
- `POST /clone`   → multipart: `text`, `ref_audio`, `ref_text`

---

## 🎧 الأصوات الجاهزة (17)

| ذكور | إناث |
| --- | --- |
| Abdelrahman, Abdullah, Kamal, Hossam, Mohamed, Omar, **Sayed**, Zaki, Aly, Essam, Ahmed | Asmaa, Esraa, Hanan, Sarah, **Yasmin**, Omnia |

> «Sayed» (شبابي/معبّر) و«Yasmin» (شبابي/مشرق) مناسبين جداً للإعلانات.

---

## ⚙️ المحركات

| المحرك | متى تستخدمه | المتطلب |
| --- | --- | --- |
| `remote` (افتراضي) | تجارب سريعة، من غير كارت | إنترنت + كوتة Space |
| `server` | **الإنتاج** — جهازك يبعت للـ GPU السحابي | سيرفر GPU (شوف `deploy/`) |
| `local` | تشغيل على كارت NVIDIA عندك | GPU محلي (8GB+) |

التبديل عن طريق متغيّر البيئة `TTS_ENGINE`:

```powershell
# يشتغل على السيرفر السحابي
$env:TTS_ENGINE = "server"
$env:TTS_SERVER_URL = "https://xxxxx-8000.proxy.runpod.net"
$env:TTS_SERVER_TOKEN = "التوكن"
```

---

## ☁️ التشغيل على GPU سحابي

الموديل محتاج ~6–8GB VRAM. أسهل طريق:
1. اعمل GPU Pod على **RunPod** (RTX 4090 / L4 / A40).
2. `bash deploy/setup_gpu.sh` ثم `bash deploy/run_server.sh`.
3. من جهازك: `TTS_ENGINE=server` + الرابط + التوكن.

**التفاصيل الكاملة في [`deploy/README.md`](deploy/README.md)** (RunPod + Vast.ai + Docker).

### كوتة الـ Space المجاني
النسخة المجانية (ZeroGPU) بكوتة محدودة وممكن ترفض الطلبات. حلول:
- تعيين `HF_TOKEN` (توكن HuggingFace) → كوتة أعلى.
- تشغيل محرك محلي على GPU.
- استئجار GPU سحابي (RunPod / Vast.ai) وتشغيل `LocalVoiceTutEngine`.

---

## 📋 الخطوات الجاية

1. توفير GPU (محلي أو سحابي) → تشغيل `LocalVoiceTutEngine`.
2. توسيع `backend/text/normalize.py` (قواميس نطق أسماء/كلمات أجنبية + تشكيل الكلمات الملتبسة).
3. إضافة `pyloudnorm` لمعالجة EBU R128 (-14 LUFS).
4. مسار fine-tune لاستنساخ «نفس الأداء الصوتي» من تسجيلات العميل.
5. واجهة مستخدم (Gradio / Next.js).

---

## ⚖️ قانوني (مهم للتجاري)

- موافقة **مكتوبة** من صاحب أي صوت حقيقي قبل الاستنساخ.
- إفصاح إن الصوت مصطنع عند اللزوم.
- ممنوع استنساخ أصوات مشاهير/أشخاص بدون إذن، أو استخدامها في تضليل/انتحال.
