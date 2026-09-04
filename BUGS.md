# الأخطاء المكتشفة أثناء كتابة الاختبارات

> تم اكتشاف هذه الأخطاء كتبا بجانب كتابة الاختبارات الشاملة (`tests/`) والتحقق من سلوك الكود الفعلي.
> الحالة: **السلوك الحالي مؤمَّن (pinned) باختبارات مرجعية** — رمز التطبيق لم يُعدَّل.

- **حجم المجموعة:** 143 اختبارًا، كلها ناجحة.
- **المرجع:** `BUGS.md` يسجل الأخطاء الوظيفية فقط. الأخطاء الخاصة بـ UI (مثل نوافذ customtkinter) خارج النطاق لأنها تتطلب عرض رسومي.

---

## 1. [BUG] رابط `youtu.be/<id>` المختصر غير معترف به (اعتدال: عالي)

- **الملف:** `utils/validators.py:3-9`
- **الوصف:** `YOUTUBE_RE` يتطلب وجود مسار واحد من `/watch?v=`, `/embed/`, `/v/`, `/shorts/`, `/playlist?list=`, `/watch?.*list=` بعد النطاق. لذلك روابط `youtu.be/<id>` المختصرة (أكثر روابط المشاركة شيوعًا) **لا تُطابَق** وتُرفض.
- **السلوك الفعلي:**
  ```python
  is_valid_youtube_url("https://youtu.be/dQw4w9WgXcQ")  # → False ❌
  is_valid_youtube_url("http://youtu.be/dQw4w9WgXcQ")   # → False ❌
  ```
- **الأثر:** لا يمكن إضافة الفيديو عبر الروابط المختصرة من صفحة المشاركة.
- **الاختبار المرجعي:** `tests/test_validators.py` → `test_bare_youtu_be_short_links_are_rejected_by_current_regex`

---

## 2. [BUG] أزرار `watch?v=short` — معرّف الفيديو اختياري وغير مثبّت في نهاية النمط (اعتدال: عالي)

- **الملف:** `utils/validators.py:8`
- **الوصف:** المجموعة `([\w-]{11})?` اختيارية (علامة `?`) وغير مرساة بنهاية النمط، لذا يمر حتى معرّف قصير أو غائب.
- **السلوك الفعلي:**
  ```python
  is_valid_youtube_url("https://youtube.com/watch?v=short")  # → True ❌ (يجب False)
  is_valid_youtube_url("https://youtube.com/watch?v=")        # → True ❌
  ```
- **الأثر:** أي URL متشابه الشكل يُقبل، مما يمرر روابط غير صالحة للمعالجة، ويجعل `is_valid_youtube_url` أضعف من اسمها.
- **الاختبار المرجعي:** `tests/test_validators.py` → `test_short_video_id_still_accepted_because_group_is_optional`

---

## 3. [BUG] فرع `except UnsupportedError` ميت (dead code) — رسالة "unsupported_url" لا تُرسل أبدًا (اعتدال: حرج)

- **الملف:** `core/download_controller.py:62-65`
- **الوصف:** في مكتبة `yt-dlp`، `UnsupportedError` **يرث من `ExtractorError`**. لذلك يلتقط الفرع `except ExtractorError` (سطر 62) كل أخطاء `UnsupportedError` قبل الوصول إلى `except UnsupportedError` (سطر 64)، مما يجعل ذلك الفرع غير قابل للوصول.
- **السلوك الفعلي:**
  ```python
  # رفع UnsupportedError من ydl.download() يؤدي إلى:
  self._queue.put(("error", "extractor:Unsupported URL: ..."))  # وليس ("unsupported_url")
  ```
- **الأثر:** واجهة المستخدم لن تعرف أبدًا أن الرابط غير مدعوم وتظهر برسالة "extractor:..." بدلاً من رسالة واضحة.
- **الاختبار المرجعي:** `tests/test_download_controller.py` → `test_unsupported_error_is_caught_as_extractor_error`

---

## 4. [BUG] رسائل `ExtractorError` تحمل لاحقة yt-dlp القياسية — نص ملوّث للمستخدم (اعتدال: متوسط)

- **الملف:** `core/download_controller.py:63`
- **الوصف:** `str(ExtractorError)` في yt-dlp تُلحق الجملة المعيارية `"; please report this issue at https://github.com/yt-dlp/yt-dlp/issues"` بكل رسالة.
- **السلوك الفعلي:**
  ```python
  # رفع ExtractorError("extractor blew up") يعطي:
  "extractor:extractor blew up; please report this issue at https://..."
  ```
- **الأثر:** رسالة خطأ طويلة وغير مفيدة تصل إلى المستخدم.
- **الاختبار المرجعي:** `tests/test_download_controller.py` → `test_extractor_error_is_prefixed_with_suffix_in_message`

---

## 5. [BUG] مفاتيح `FORMAT_MAP` بصيغة lowercase بينما واجهة المستخدم "Best" (اعتدال: متوسط)

- **الملف:** `core/format_builder.py:1-9, 17-29`
- **الوصف:** `QUALITY_OPTIONS[0] == "Best"` لكن `FORMAT_MAP` يحتوي على المفتاح `"best"` فقط (بدون "Best"). أي كود يصل مباشرةً إلى `FORMAT_MAP["Best"]` يصطدم بـ `KeyError`.
- **السلامة الحالية:** `build_format_opts` تتعامل معها عبر `quality.lower()`، لكن المفتاح غير الموجود يسقط بصمت إلى `FORMAT_MAP["best"]` بدلاً من رفع خطأ واضح (سلوك صامت محفوف بالمخاطر).
- **السلوك الفعلي:**
  ```python
  build_format_opts("Best", "video")       # يعمل ✅ (عبر .lower())
  FORMAT_MAP["Best"]                        # KeyError ❌
  build_format_opts("UNKNOWN", "video")    # يسقط صامتًا إلى "best" بدون تحذير
  ```
- **الأثر:** فصل هش بين قيمة الواجهة والقواميس؛ أي مُستدعي جديد قد يكسر عند استعمال "Best".
- **الاختبار المرجعي:** `tests/test_format_builder.py` → `test_quality_options_are_prescribed_order` و `test_video_mode_unknown_quality_falls_back_to_best`

---

## 6. [BUG] `extract_title` قد تُرجع `None` رغم التوقيع `-> str` (اعتدال: منخفض)

- **الملف:** `core/info_extractor.py:40-41`
- **الوصف:** `info.get("title", "")` تُرجع القيمة `None` إذا كان المفتاح موجودًا بقيمة `None` بدلاً من الرجوع إلى `""`. ينطبق الأمر أيضًا على `extract_thumbnail`, `extract_duration` (قد تُرجع None), `extract_uploader`.
- **السلوك الفعلي:**
  ```python
  extract_title({"title": None})  # → None ❌ (التوقيع يعد بـ str)
  extract_title({})               # → "" ✅
  ```
- **الأثر:** أي سطر لاحق يفترض `str` (مثل `.strip()` أو concat) قد ينفجر بمجرد وجود مفتاح بقيمة None في بيانات yt-dlp.
- **الاختبار المرجعي:** `tests/test_info_extractor.py` → `test_extract_title` (مع حالات None).

---

## 7. ملاحظة سلوكية (ليست خطأ): دلالات `get_available_qualities`

- **الملف:** `core/info_extractor.py:32-33`
- **الوصف:** تُرجع "Best" + كل درجة مُعدّة تكون عتبتها `<=` أعلى ارتفاع موجود في الفيديو. أي أن فيديو 1080p يعطي `[Best, 1080p, 720p, 480p, 360p, 240p]` (تُستثنى 1440p/2160p). هذه دلالة "حد أقصى" مقصودة — ليست خطأ، لكن موثقة حتى يدرك المصممون المعنى.
- **الاختبار المرجعي:** `tests/test_info_extractor.py` → `test_get_available_qualities_derives_from_heights`

---

## 8. ملاحظة فرعية: `PATH` تُعدَّل بشكل دائم

- **الملف:** `core/download_controller.py:38-40` و `core/format_builder.py` (`get_common_opts`)
- **الوصف:** عند نجاح `ffmpeg_location` تُضاف مجلد `bin/` إلى `os.environ["PATH"]` بدون تنظيف عكسي بعد التحميل. التأثير عمليًا طفيف (مجلد ثابت موجود)، لكنه تراكمي عبر الجلسات إذا بدّل المستخدم مواقع `bin/`.
- **الاختبار المرجعي:** `tests/test_format_builder.py` → `test_get_common_opts_sets_bin_dir_into_path`

---

## ملخص الأولويات

| # | الملف | الخطأ | الأولوية | الاختبار المرجعي |
|---|-------|-------|----------|------------------|
| 1 | `utils/validators.py` | رفض روابط `youtu.be/<id>` المختصرة | عالي | `test_bare_youtu_be_short_links_are_rejected_by_current_regex` |
| 2 | `utils/validators.py` | قبول معرّف قصير/غائب (`watch?v=short`) | عالي | `test_short_video_id_still_accepted_because_group_is_optional` |
| 3 | `core/download_controller.py` | فرع `UnsupportedError` ميت → "unsupported_url" لا تُرسل | حرج | `test_unsupported_error_is_caught_as_extractor_error` |
| 4 | `core/download_controller.py` | لاحقة yt-dlp في رسائل ExtractorError | متوسط | `test_extractor_error_is_prefixed_with_suffix_in_message` |
| 5 | `core/format_builder.py` | مفاتيح lowercase vs "Best" + سقوط صامت | متوسط | `test_quality_options_are_prescribed_order` |
| 6 | `core/info_extractor.py` | `extract_title`/`extract_duration` قد تُرجع None | منخفض | `test_extract_title` |