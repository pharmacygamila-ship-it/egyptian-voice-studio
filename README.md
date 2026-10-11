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
├─ batch_generate.py           توليد دفعي لكل الإعلانات
├─ .env.example                مثال إعدادات
├─ frontend/index.html         واجهة الويب (RTL)
├─ backend/
│   ├─ main.py                 FastAPI (/health /voices /tts /clone) + حماية توكن
│   ├─ engine/
│   │   ├─ base.py             الواجهة المشتركة
│   │   ├─ factory.py          اختيار المحرك (TTS_ENGINE)
│   │   ├─ remote_voicetut.py  محرك أونلاين (الـ Space)
│   │   ├─ server_client.py    عميل سيرفر GPU بتاعنا
│   │   └─ local_voicetut.py   محرك محلي/GPU
│   ├─ text/
│   │   ├─ normalize.py        تطبيع النص المصري (المدخل الرئيسي)
│   │   ├─ numbers.py          الأرقام → كلام مصري (خمسين / ألفين…)
│   │   └─ lexicon.py          نطق الأجنبي + الوحدات (واتساب / كيلوجرام)
│   └─ audio/postprocess.py    معالجة صوت إعلانية
├─ deploy/
│   ├─ README.md               خطوات RunPod / Vast.ai / Docker / Colab / Modal
│   ├─ setup_gpu.sh            تجهيز بيئة GPU
│   ├─ run_server.sh           تشغيل السيرفر
│   ├─ docker-compose.yml
│   ├─ colab_free_gpu.ipynb    Notebook للـ Colab المجاني
│   └─ modal_app.py            نشر على Modal (رصيد مجاني)
├─ tests/
│   ├─ selfcheck.py            فحص المكونات
│   ├─ test_text.py            فحص طبقة النص المصري (أرقام/نطق/تنضيف)
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

ثم افتح الواجهة في المتصفح: **http://127.0.0.1:8000/**

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

### 🆓 مجاناً (بدون بطاقة)
- **Colab / Kaggle** — GPU T4 مجاني للتوليد الدفعي → `deploy/colab_free_gpu.ipynb`
- **Modal** — $30/شهر رصيد لسيرفر API دائم → `deploy/modal_app.py`
- **HF Space** — تجارب سريعة (كوتة محدودة) → المحرك `remote`

### 🔁 توليد دفعي
```powershell
# محلياً (عبر السيرفر) أو على Colab/Kaggle (محرك محلي)
.\.venv\Scripts\python.exe batch_generate.py --speaker Sayed --zip ads.zip
```
سمّي الملف `ad2__Yasmin.txt` لو عايز صوت مختلف لكل إعلان.

### كوتة الـ Space المجاني
النسخة المجانية (ZeroGPU) بكوتة محدودة وممكن ترفض الطلبات. حلول:
- تعيين `HF_TOKEN` (توكن HuggingFace) → كوتة أعلى.
- تشغيل محرك محلي على GPU.
- استئجار GPU سحابي (RunPod / Vast.ai) وتشغيل `LocalVoiceTutEngine`.

---

## 🗣️ طبقة النص المصري

كل نص بيمر على `backend/text/normalize.py` قبل التوليد:

| الخطوة | مثال |
| --- | --- |
| أرقام شرقية → غربية | `٥٠` → `50` |
| أرقام → كلام مصري | `50` → **خمسين** · `2026` → **ألفين وستة وعشرين** |
| أرقام طويلة (تليفون) رقم رقم | `01001234567` → **صفر واحد صفر…** |
| أوقات / كسور | `3:30` → **تلاتة وتلاتين** · `3.5` → **تلاتة فاصلة خمسة** |
| نسب | `50%` → **خمسين في المية** |
| نطق الأجنبي | `WhatsApp` → **واتساب** · `order` → **أوردر** |
| وحدات ملزوقة | `5kg` → **خمسة كيلوجرام** |
| تنضيف | إيموجي + تطويل (`حلوووو` → `حلو`) |

التحكم:
```python
from backend.text.normalize import normalize_egyptian
normalize_egyptian("خصم 50%")                       # → "خصم خمسين في المية"
normalize_egyptian("٥٠", numbers=False)             # → "50"  (من غير كلام)
normalize_egyptian("WhatsApp", use_lexicon=False)   # → "WhatsApp"
```

**تعديل القاموس:** `backend/text/lexicon.py` (كلمات أجنبية/وحدات) و `backend/text/numbers.py` (صيغ الأرقام).

---

## 📋 الخطوات الجاية

1. توفير GPU (محلي أو سحابي) → تشغيل `LocalVoiceTutEngine`.
2. تشكيل الكلمات الملتبسة (diacritization) + توسيع قاموس الأسماء والبراندات.
3. إضافة `pyloudnorm` لمعالجة EBU R128 (-14 LUFS).
4. مسار fine-tune لاستنساخ «نفس الأداء الصوتي» من تسجيلات العميل.
5. واجهة مستخدم (Gradio / Next.js).

---

## ⚖️ قانوني (مهم للتجاري)

- موافقة **مكتوبة** من صاحب أي صوت حقيقي قبل الاستنساخ.
- إفصاح إن الصوت مصطنع عند اللزوم.
- ممنوع استنساخ أصوات مشاهير/أشخاص بدون إذن، أو استخدامها في تضليل/انتحال.
