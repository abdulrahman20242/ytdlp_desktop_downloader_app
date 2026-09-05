# سجل الأخطاء المكتشفة وإصلاحها

> سجل الأخطاء الوظيفية المكتشفة أثناء كتابة الاختبارات (`tests/`)، مع إصلاحاتها وحالة كل منها.
>
> **آخر تحديث:** بعد جلسة الإصلاح.
> **حجم المجموعة:** 157 اختبارًا، كلها ناجحة + `ruff check` نظيف على `core/ utils/ ui/ tests/`.

---

## ✅ الأخطاء التي تم إصلاحها (6/6)

### 1. رابط `youtu.be/<id>` المختصر غير معترف به

- **الملف:** `utils/validators.py:3-9`
- **المشكلة:** `YOUTUBE_RE` يتطلب مسارًا (`/watch?v=`...) بعد النطاق، فلا تُطابَق روابط `youtu.be/<id>`.
- **الإصلاح:** أُعيد بناء النمط ليشمل فرع `/([\w-]{11})` المختصر لأجل `youtu.be/<id>` (+ دعم `?param`).
- **التحقق:** `tests/test_validators.py` → `test_bare_youtu_be_short_links_are_accepted`، وإضافات في `test_detects_valid_youtube_url`.

### 2. `watch?v=short` مقبول — معرّف الفيديو اختياري وغير مثبّت

- **الملف:** `utils/validators.py:8`
- **المشكلة:** المجموعة `([\w-]{11})?` اختيارية وغير مرساة، فيمر أي معرّف قصير/غائب/طويل.
- **الإصلاح:** المعرّف الآن إلزامي (بدون `?`) ويليه نظرة سلبية `(?![\w-])` تضبطه على **11 حرفًا بالضبط**؛ فأصبح `watch?v=short` و `watch?v=` و معرّفٌ أطول من 11 حرفًا كلها مرفوضة.
- **التحقق:** `tests/test_validators.py` → `test_short_or_malformed_video_id_is_rejected`.

### 3. فرع `except UnsupportedError` ميت — "unsupported_url" لا تُرسل

- **الملف:** `core/download_controller.py:62-65`
- **المشكلة:** `UnsupportedError` يرث من `ExtractorError`، فالفرع الخاص به لا يُنفَّذ أبدًا.
- **الإصلاح:** أعيد ترتيب المعالجات: `except UnsupportedError` **قبل** `except ExtractorError` → الآن يصل `unsupported_url` للمستخدم عند رابط غير مدعوم.
- **التحقق:** `tests/test_download_controller.py` → `test_unsupported_error_fires_unsupported_url_sentinel`.

### 4. لاحقة yt-dlp القياسية في رسائل `ExtractorError`

- **الملف:** `core/download_controller.py:63`
- **المشكلة:** `str(ExtractorError)` تحمل `; please report this issue ...` فيظهر نص طويل للمستخدم.
- **الإصلاح:** دالة `_strip_ytdlp_report_suffix()` تُزيل اللاحقة عند العلامة `"; please report this issue"` قبل عرض الرسالة.
- **التحقق:** `tests/test_download_controller.py` → `test_extractor_error_message_strips_ytdlp_boilerplate_suffix`.

### 5. مفاتيح `FORMAT_MAP` صغيرة بينما الواجهة "Best"

- **الملف:** `core/format_builder.py:17-33`
- **المشكلة:** `FORMAT_MAP["Best"]` يرمي `KeyError` لأن المفاتيح `"best"` فقط؛ مع سقوط صامت للجودة المجهولة.
- **الإصلاح:** أُضيف مفتاحا `"Best"` إلى `FORMAT_MAP` و `FORMAT_MAP_MP4` (قيمة مساوية لـ `"best"`). السقوط الصامت للمفاتيح المجهولة أُبقي عمدًا كسلوك دفاعي موثّق.
- **التحقق:** `tests/test_format_builder.py` → `test_format_maps_expose_best_alias`.

### 6. `extract_title`/`extract_duration` تعيدان `None` رغم التوقيع `-> str`

- **الملف:** `core/info_extractor.py:36-49` (وأثرها في `ui/main_window.py:202-207`)
- **المشكلة:** `info.get("title", "")` تعيد `None` إذا كان المفتاح موجودًا بقيمة `None`.
- **الإصلاح:** استُبدلت بالصيغة `info.get(...) or <default>` في المساعدين الأربعة (`title`, `duration`, `uploader`, `thumbnail`)، وحُدّث `main_window` ليستخدم المساعدين بدل `info.get(...)` المباشر حتى لا يمر `None` للواجهة.
- **التحقق:** `tests/test_info_extractor.py` → حالات `None` جديدة في `test_extract_title/duration/uploader/thumbnail`.

---

## ⚠️ ملاحظات متبقية لم تُصلَح (ليست أخطاء وظيفية، أو منخفضة الأولوية)

### 7. دلالات `get_available_qualities` — "حدّ أقصى" مقصودة

- **الحالة:** **لم تُصلَح عمدًا — سلوك مقصود.**
- **الملف:** `core/info_extractor.py:32-33`
- **الشرح:** تُرجع "Best" + كل درجة عتبتها `<=` أعلى ارتفاع موجود. فيديو 1080p يعطي `[Best, 1080p, 720p, ...]` (دون 1440p/2160p). موثّقة حتى يدرك المصممون المعنى.

### 8. تعديل `PATH` الدائم بإضافة مجلد `bin/`

- **الحالة:** **موجودة — منخفضة الأولوية، أُبقي كما هو عمدًا.**
- **الملف:** `core/format_builder.py:88-89` (ويوجد مثيل مشابه في `core/download_controller.py:38-40`)
- **الشرح:** تُضاف `bin/` إلى `os.environ["PATH"]` دون تنظيف عكسي بعد التحميل. الحارس `if bin_path not in current_path` يمنع التكرار في نفس الجلسة؛ الأثر عمليًا طفيف (مجلد ثابت). الإصلاح الكامل (استعادة PATH) له قيمة منخفضة مقابل تعقيد إضافي.

### 9. حدود `extract_video_id` و `PLAYLIST_RE` على النطاقين

- **الحالة:** **موجودة — خارج نطاق الإصلاحات الحالية.**
- **الملف:** `utils/validators.py:29-30` و `11-17`
- **الشرح:**
  - `extract_video_id` يستخدم `re.search` بلا نظرة سلبية، فمعرّف أطول من 11 حرفًا على `youtu.be/<id>` (*نادر في الواقع*) يُرجع أول 11 حرفًا فقط.
  - `PLAYLIST_RE` يتقبل نطاق `youtube.com` فقط؛ رابط `youtu.be/...?list=...` لا يُصنَّف كقائمة تشغيل.

---

## الأثر الإجمالي

| الملف | قبل | بعد |
|-------|-----|-----|
| `utils/validators.py` | روابط `youtu.be` مرفوضة، معرّفات قصيرة مقبولة | الروابط المختصرة تعمل، المعرّف مضبوط على 11 حرفًا |
| `core/download_controller.py` | فرع `UnsupportedError` ميت، رسائل Extract قذرة | `unsupported_url` تصل، الرسائل نظيفة |
| `core/format_builder.py` | `FORMAT_MAP["Best"]` = KeyError | مفتاح `"Best"` موجود |
| `core/info_extractor.py` + `ui/main_window.py` | `title/duration/uploader` قد تكون `None` | قيم افتراضية مضمونة النوع |
| `tests/` | 143 اختبارًا تُثبّت السلوك المعيب | 157 اختبارًا تُثبّت السلوك السليم |