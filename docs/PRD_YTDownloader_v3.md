# PRD — YT Downloader Desktop Application
### Version 3.0 | ReizanTech | Sep 2026

---

## فهرس المحتويات

1. [نظرة عامة](#1-نظرة-عامة)
2. [الهدف والمشكلة](#2-الهدف-والمشكلة)
3. [الجمهور المستهدف](#3-الجمهور-المستهدف)
4. [التقنيات المستخدمة](#4-التقنيات-المستخدمة)
5. [متطلبات النظام](#5-متطلبات-النظام)
6. [المعمارية الهندسية](#6-المعمارية-الهندسية)
7. [نموذج الـ Threading](#7-نموذج-الـ-threading)
8. [الميزات الأساسية MVP](#8-الميزات-الأساسية-mvp)
9. [منطق اختيار الصيغة](#9-منطق-اختيار-الصيغة)
10. [نظام تتبع التقدم](#10-نظام-تتبع-التقدم)
11. [الإعدادات — config.json](#11-الإعدادات--configjson)
12. [فحص التبعيات عند التشغيل](#12-فحص-التبعيات-عند-التشغيل)
13. [معالجة الأخطاء](#13-معالجة-الأخطاء)
14. [بنية المشروع](#14-بنية-المشروع)
15. [بناء الـ EXE](#15-بناء-الـ-exe)
16. [الميزات المستقبلية](#16-الميزات-المستقبلية)
17. [قرارات معمارية — ADRs](#17-قرارات-معمارية--adrs)
18. [KPIs ومعايير النجاح](#18-kpis-ومعايير-النجاح)
19. [نطاق المشروع](#19-نطاق-المشروع)

---

## 1. نظرة عامة

**YT Downloader** تطبيق Desktop يعمل على Windows، مبني بـ Python مع واجهة `customtkinter`، يتيح تحميل الفيديوهات والصوت والـ Playlists من YouTube بكفاءة عالية.

التطبيق يستخدم محركَين منفصلين:
- **التحميل:** تنفيذ `bin/yt-dlp.exe` كـ **subprocess** مع قراءة مخرجات `--newline --progress` وتحليلها بـ regex (لا `YoutubeDL.download()` مباشرة).
- **استخراج المعلومات:** Python API (`yt_dlp.YoutubeDL` مع `download=False`) لعرض العنوان والصورة والجودات.

---

## 2. الهدف والمشكلة

### المشكلة
لا يوجد تطبيق Desktop بسيط وموثوق يدعم YouTube الحديث (التغلب على JavaScript challenges، المحتوى المقيّد بالعمر، الـ Playlists) مع واجهة عربية/إنجليزية واضحة.

### الهدف
تقديم تجربة تحميل سلسة تدعم:
- أعلى جودة متاحة (حتى 4K)
- تحويل صوت بكودك احترافي (MP3 / M4A)
- تحميل Playlists بالكامل مع لوحة تحكم في الواجهة
- دعم YouTube الحديث عبر Node.js + yt-dlp-ejs
- واجهة لا تتجمد أثناء التحميل

---

## 3. الجمهور المستهدف

### 3.1 المستخدم العادي
- يريد تحميل فيديو أو صوت بضغطة واحدة
- لا يهمه الإعدادات التقنية
- يتوقع واجهة واضحة ونتيجة سريعة

### 3.2 المستخدم المتقدم
- يحدد الجودة والصيغة يدوياً
- يحمّل Playlists مع تنظيم المجلدات
- يستخدم cookies للمحتوى المقيّد
- يريد رؤية الـ Logs بالتفصيل

---

## 4. التقنيات المستخدمة

| الجزء | التقنية | الإصدار المطلوب | الملاحظة |
|---|---|---|---|
| اللغة | Python | 3.11+ | CPython فقط |
| GUI | customtkinter | 5.x | يبنى فوق tkinter |
| Downloader | yt-dlp (EXE) | lastest من releases | `bin/yt-dlp.exe` يُنفَّذ كـ subprocess |
| Info API | yt-dlp (Python) | `>=2025.1.1` | `yt_dlp.YoutubeDL` بـ `download=False` |
| Media Processing | FFmpeg + FFprobe | من yt-dlp/FFmpeg-Builds | `bin/ffmpeg.exe` + `bin/ffprobe.exe` |
| JS Support | yt-dlp-ejs + Node.js | ≥0.8.0 / Node موجود | Plugin عبر `--extractor-args youtube-ejs` + `--js-runtimes` |
| Packaging | PyInstaller | 6.x (مخطط) | `--onedir` — `build.spec` غير موجود بعد |

> **ملاحظة:** `yt-dlp-ejs` هو plugin لـ yt-dlp (لا يُستورد في Python). يُفعَّل عبر تمرير `--extractor-args youtube-ejs` و `--js-runtimes node:<bin>/node.exe` في الأمر CLI.

---

## 5. متطلبات النظام

### 5.1 بيئة التشغيل
- Windows 10 / 11 (x64)
- Python 3.11+
- Node.js (اختياري — مطلوب لحل JavaScript challenges في بعض فيديوهات YouTube)
- FFmpeg + FFprobe (مطلوبان — الدمج والـ probing)

### 5.2 ملفات الـ Binaries

```
project/
├── bin/
│   ├── yt-dlp.exe         ← محرك التحميل (يُنفَّذ كـ subprocess)
│   ├── ffmpeg.exe         ← من yt-dlp/FFmpeg-Builds (دمج + تحويل الصوت)
│   ├── ffprobe.exe        ← نفس المصدر (فحص الوسائط)
│   └── node.exe           ← Node.js standalone (JS runtime لـ yt-dlp-ejs)
```

> **ملاحظة:** `yt-dlp.exe` هو **محرك التحميل الفعلي** في هذه النسخة. أما `ffmpeg.exe` و`node.exe` فيحتاجهما yt-dlp داخلياً كـ subprocess.

### 5.3 الملفات الاختيارية

```
project/
└── data/
    └── cookies.txt        ← اختياري، للمحتوى المقيّد
```

---

## 6. المعمارية الهندسية

```
┌──────────────────────────────────────────────────────────┐
│                        UI Layer                           │
│  MainWindow (CTkFrame) · SettingsDialog (CTkToplevel)     │
│  ProgressWidget · LogsPanel · QualitySelector             │
│  PlaylistPanel · StartupCheckFrame                        │
└─────────────────────┬────────────────────────────────────┘
                      │  events / callbacks via queue.Queue
┌─────────────────────▼────────────────────────────────────┐
│                  Controller Layer                         │
│  DownloadController · InfoExtractor                       │
│  ConfigManager · DependencyChecker · FormatBuilder        │
└──────┬──────────────────────────────┬────────────────────┘
       │ subprocess.Popen             │ python yt_dlp API
┌──────▼───────────────┐    ┌─────────▼─────────────┐
│  Download Engine     │    │  Info Extraction      │
│  bin/yt-dlp.exe      │    │  yt_dlp.YoutubeDL     │
│  (CLI، stdout يُقرأ   │    │  (download=False،     │
│   سطراً بسطر)        │    │   يستخرج metadata)    │
└──────┬───────────────┘    └─────────┬─────────────┘
       │                              │
┌──────▼──────────────────────────────▼──────────────┐
│   bin/ffmpeg.exe  bin/ffprobe.exe  bin/node.exe     │
└─────────────────────────────────────────────────────┘
```

### 6.1 القاعدة المحورية: Subprocess للتحميل — Python API للاستخراج فقط

```python
# ✅ تحميل الفيديو (الطريقة المعتمدة) — subprocess مع تحليل stdout
import subprocess
from core.download_controller import _build_argv

argv = _build_argv(opts, url, save_dir)      # يبني flags من dict الـ opts
proc = subprocess.Popen(
    [str(self._exe_path(opts)), *argv],      # bin/yt-dlp.exe
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True, encoding="utf-8", errors="replace",
)
for raw in proc.stdout:                      # قراءة سطر بسطر
    line = _strip_ansi(raw).rstrip("\r\n")
    if line.startswith("ERROR:"):   → event "error"
    if line.startswith("WARNING:"): → event "log"
    prog = _parse_progress(line)    → event "progress"   # [download] 45.3%
    ...

# ❌ لم يُعتمد — YoutubeDL.download() المباشرة في هذه النسخة
from yt_dlp import YoutubeDL
with YoutubeDL(opts) as ydl:
    ydl.download([url])

# ✅ استخراج المعلومات فقط (Python API) — لا تحميل
from yt_dlp import YoutubeDL
opts = {"quiet": True, "no_warnings": True, "download": False}
with YoutubeDL(opts) as ydl:
    info = ydl.extract_info(url, download=False)
```

**لماذا subprocess للتحميل؟**
- فصل محرك التحميل عن نسخة الـ Python API → تحديث `bin/yt-dlp.exe` مستقلاً
- تحكم مباشر في العملية (`terminate()`) عند الإلغاء
- معالجة دمج الـ video+audio ومنتجه النهائي تتم بواسطة `bin/yt-dlp.exe` نفسه
- أخطاء الـ extractor تعود كنص stdout يمكن تصنيفه بدقة (`_classify_error`)

---

## 7. نموذج الـ Threading

**المشكلة الأساسية:** التحميل عملية blocking — لو اشتغل في Main Thread سيجمّد الـ GUI.

**الحل:** كل عملية تحميل تشتغل في `threading.Thread` منفصل، والتواصل مع الـ GUI عبر `queue.Queue`.

```python
import threading
import queue

class DownloadController:
    def __init__(self, config):
        self._queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._proc = None                      # subprocess الحالي

    def start_download(self, url, opts, save_dir):
        """فيديو واحد — يبدأ _download_worker في thread منفصل"""
        self._thread = threading.Thread(
            target=self._download_worker, args=(url, opts, save_dir), daemon=True)
        self._thread.start()

    def start_playlist_download(self, entries, opts, save_dir):
        """Playlist — يبدأ _playlist_worker ويرسل playlist_item لكل عنصر"""
        self._thread = threading.Thread(
            target=self._playlist_worker, args=(entries, opts, save_dir), daemon=True)
        self._thread.start()

    def _download_worker(self, url, opts, save_dir):
        result = self._run_single(url, opts, save_dir)   # subprocess + parsing
        if result == "ok":
            self._queue.put(("done", None))
        else:
            self._queue.put(("error", result))

    def _poll_queue(self):
        """يعمل في Main Thread عبر app.after(100) — يقرأ الأحداث"""
        # events: progress / done / error / log / playlist_item / playlist_done

    def cancel(self):
        self._stop_event.set()
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()             # إنهاء subprocess
```

الأحداث المدعومة:
| الحدث | المعنى |
|---|---|
| `progress` | نسبة مئوية + سرعة + ETA (من stdin) |
| `done` | اكتمل فيديو واحد |
| `error` | فشل بتصنيف `_classify_error` |
| `log` | سطر INFO/WARNING/ERROR من yt-dlp |
| `playlist_item` | تحديث حالة عنصر داخل الـ Playlist |
| `playlist_done` | انتهاء الـ Playlist بالكامل |

---

## 8. الميزات الأساسية MVP

### 8.1 تحميل فيديو

**تدفق الاستخدام:**
1. المستخدم يلصق الرابط
2. `utils/validators.py` يتحقق من الرابط (regex + استخراج video ID بطول 11 حرفاً)
3. `info_extractor.extract_info(url)` يستخرج المعلومات (`download=False`) ويعرض العنوان والصورة المصغرة والقناة والمدة
4. المستخدم يختار الجودة والصيغة
5. يضغط Download → `DownloadController.start_download()`
6. يقرأ الـ thread سطراً بسطر من stdout ويحدّث الـ Progress Bar
7. بعد الانتهاء: إشعار نجاح + زر فتح المجلد

**الأمثلة لـ yt-dlp opts (video):**
```python
{
    'format': FORMAT_MAP[quality],             # انظر القسم 9
    'merge_output_format': 'mp4',
    'outtmpl': str(save_dir / '%(title)s [%(id)s].%(ext)s'),
    'ffmpeg_location': str(BIN_DIR),
    'concurrent_fragments': 4,                 # تسريع HLS/DASH
    'retries': 10,
    'fragment_retries': 10,
    'throttledratelimit': 102400,              # استرداد سريع من throttling
    'format_sort': ['vcodec:h264,vp9,av01', 'res', 'br'],  # توافق أعلى
    'js_runtimes': {'node': {}},               # تفعيل yt-dlp-ejs
    'extractor_args': {'youtube-ejs': {}},
    'ignoreerrors': False,
    'quiet': False,                            # يلزم للـ progress parsing
    'noplaylist': True,                        # رابط فيديو لا يُسحب لو قائمة
}
```

### 8.2 تحميل MP3

```python
{
    'format': 'm4a/bestaudio/best',
    'outtmpl': str(save_dir / '%(title)s [%(id)s].%(ext)s'),
    'ffmpeg_location': str(BIN_DIR),
    'postprocessors': [
        {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'},
        {'key': 'FFmpegMetadata', 'add_metadata': True},
        {'key': 'EmbedThumbnail'},
    ],
    'writethumbnail': True,
}
```

### 8.3 تحميل M4A (بدون إعادة ترميز — أسرع)

```python
{
    'format': 'm4a/bestaudio/best',
    'outtmpl': str(save_dir / '%(title)s [%(id)s].%(ext)s'),
    'ffmpeg_location': str(BIN_DIR),
    'postprocessors': [
        {'key': 'FFmpegMetadata', 'add_metadata': True},
        {'key': 'EmbedThumbnail'},
    ],
    'writethumbnail': True,
}
```

### 8.4 تحميل Playlist

- استخدام `classify_url()` → playlist يتم سحبه وعرضه في `PlaylistPanel`
- `info_extractor.extract_playlist(url)` يعيد قائمة الفيديوهات (بدون تحميل)
- `start_playlist_download(entries, opts, save_dir)`:
  - يخزن كل فيديو في مجلد منفصل باسم الـ Playlist عبر `sanitize_folder_name`
  - يرسل `playlist_item` (حالة: waiting / downloading / done / error) بعد كل عنصر
  - أزرار **تنزيل الكل** و **تنزيل المحدد** في `ui/playlist_panel.py`
- كل عنصر يُحمَّل عبر `_run_single()` بآلية الفيديو الواحد نفسها

### 8.5 اختيار مجلد الحفظ

```python
save_dir = fd.askdirectory(initialdir=config.get('download.default_dir', ...))
```

الاختيار يُحفظ في `config.json` (`download.default_dir`) ويُستخدم افتراضياً. الافتراضي عند أول تشغيل: `~/Downloads/YTDownloader`.

### 8.6 Progress Bar

التقدم يُقرأ من **stdout** وليس من hooks:

```python
# core/download_controller.py
_PROGRESS_RE = re.compile(r"\[download\]\s+([\d.]+)%")   # 45.3%
_SPEED_RE    = re.compile(r"\bat\s+([^\s]+)\s+ETA")
_ETA_RE      = re.compile(r"ETA\s+([^\s)]+)")

def _parse_progress(line: str) -> dict | None:
    # → {'percent': float, 'speed': str, 'eta': str, 'filename': str}
```

عناصر الـ Progress Widget:
- `CTkProgressBar` — نسبة مئوية (0.0 → 1.0)
- Label: `45.3% · 2.3 MB/s · ETA 00:32`
- Label: اسم الملف المُحمَّل حالياً

### 8.7 Logs Panel

نافذة `CTkTextbox` قابلة للطي، تعرض:
- أسطر yt-dlp: `[INFO]`-prefix، `WARNING:` ، `ERROR:` (من stdout)
- أحداث التحميل (بدء، دمج، اكتمال)
- الأخطاء مع اقتراحات الحل

### 8.8 دعم Cookies

**خيار 1 — ملف cookies.txt** → `--cookies <file>` (`opts['cookiefile']`)
**خيار 2 — استيراد من المتصفح** → `--cookies-from-browser <chrome|firefox|edge|brave>`
**خيار 3 — بدون cookies (الافتراضي)**

> الافتراضي هو `"source": "none"` لتجنب خطأ `Could not copy Chrome cookie database` عند فتح المتصفح. عند فشل الاستخراج من المتصفح يعرض التطبيق رسالة عربية: **"فشل استخراج cookies من المتصفح — أغلق المتصفح أو استخدم ملف cookies في الإعدادات"**. الاختيار من الإعدادات → متقدم.

---

## 9. منطق اختيار الصيغة

### 9.1 جدول الـ Format Strings (من `FORMAT_MAP` في `core/format_builder.py`)

| الجودة | وضع فيديو (`FORMAT_MAP`) | وضع MP4 only (`FORMAT_MAP_MP4`) |
|---|---|---|
| Best | `bv[ext=mp4]+ba[ext=m4a]/bv+ba/b` | `bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b` |
| 2160p | `bv[height<=2160][ext=mp4]+ba[ext=m4a]/bv[height<=2160]+ba/b[height<=2160]` | `bv[height<=2160][ext=mp4]+ba[ext=m4a]/b[height<=2160]` |
| 1440p | `bv[height<=1440][ext=mp4]+ba[ext=m4a]/bv[height<=1440]+ba/b[height<=1440]` | `bv[height<=1440][ext=mp4]+ba[ext=m4a]/b[height<=1440]` |
| 1080p | `bv[height<=1080][ext=mp4]+ba[ext=m4a]/bv[height<=1080]+ba/b[height<=1080]` | `bv[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]` |
| 720p | `bv[height<=720][ext=mp4]+ba[ext=m4a]/bv[height<=720]+ba/b[height<=720]` | `bv[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]` |
| 480p | `bv[height<=480][ext=mp4]+ba[ext=m4a]/bv[height<=480]+ba/b[height<=480]` | `bv[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480]` |
| 360p | `bv[height<=360][ext=mp4]+ba[ext=m4a]/bv[height<=360]+ba/b[height<=360]` | `bv[height<=360][ext=mp4]+ba[ext=m4a]/b[height<=360]` |
| MP3 / M4A | `m4a/bestaudio/best` | — |

```python
MODE_OPTIONS = ["video", "mp4_only", "audio"]

def build_format_opts(quality: str, mode: str, config=None) -> dict:
    if mode == "audio":      # MP3 أو M4A + postprocessors + writethumbnail
        ...
    q = quality.lower()
    if mode == "mp4_only":
        opts["format"] = FORMAT_MAP_MP4.get(q, FORMAT_MAP_MP4["Best"])
    else:  # video
        opts["format"] = FORMAT_MAP.get(q, FORMAT_MAP["Best"])
        opts["merge_output_format"] = config.get("download.merge_output_format", "mp4") or "mp4"
```

> ملاحظة: القائمة المعروضة في الواجهة تشمل **"Best"** أولاً ثم الجودات (QUALITY_OPTIONS
> = `["Best", "2160p", "1440p", "1080p", "720p", "480p", "360p"]`)، وللصوت `["MP3", "M4A"]`.

### 9.2 فحص الجودات المتاحة قبل التحميل

```python
def get_available_qualities(url: str) -> list[str]:
    """يستخرج الجودات الفعلية المتاحة للفيديو — يعيد ["Best", ...]"""
    opts = {"quiet": True, "no_warnings": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        info = ydl.sanitize_info(info)

    heights = {fmt.get("height") for fmt in info.get("formats", []) if fmt.get("height")}
    thresholds = [2160, 1440, 1080, 720, 480, 360, 240]
    qs = [f"{h}p" for h in thresholds if any(x >= h for x in heights)]
    return ["Best"] + qs   # ← "Best" تُضاف دائماً في البداية
```

### 9.3 ترتيب ترميز الفيديو (format_sort)

بدون `format_sort`، yt-dlp يختار `av01 > vp9 > avc1` أي `398+251` (av01+opus) بدلاً من `136+140` (avc1+m4a).

```python
opts['format_sort'] = ['vcodec:h264,vp9,av01', 'res', 'br']
```

### 9.4 مقاومة Throttling

```python
opts['throttledratelimit'] = 102400   # 100 KB/s — yt-dlp يعيد الاستخراج تلقائياً
```

### 9.5 JavaScript Runtime (yt-dlp-ejs)

```python
opts['js_runtimes'] = {'node': {}}                 # يُصبح --js-runtimes node:<bin>/node.exe
opts['extractor_args'] = {'youtube-ejs': {}}       # يُصبح --extractor-args youtube-ejs
```

---

## 10. نظام تتبع التقدم

### 10.1 المصدر: stdout بدلاً من progress hooks

التطبيق ينفذ `bin/yt-dlp.exe` مع `--newline --progress` ويقرأ stdout سطراً بسطر:

```python
# أقسام السطر الواحد:
# [download] Destination: <path>                  → _parse_destination → filename
# [download]  45.3% of 100.00MiB at 2.30MiB/s ETA 00:32 → _parse_progress
# [info] <title>                                  → log
# WARNING: ...                                    → log
# ERROR: ...                                      → error

def _parse_progress(line):
    m = _PROGRESS_RE.search(line)                 # [download] 45.3%
    speed = _SPEED_RE.search(line)                # at 2.30MiB/s ETA
    eta   = _ETA_RE.search(line)                  # ETA 00:32
    ...
```

### 10.2 حساب نسبة التقدم بشكل آمن

```python
percent = float(prog["percent"])   # من regex مباشرة، مقيدة بـ min(.., 100)
```

---

## 11. الإعدادات — config.json

### 11.1 المخطط الكامل (القيم الفعلية من `_DEFAULTS`)

```json
{
  "version": "1.0",
  "ui": {
    "theme": "dark",
    "language": "ar",
    "window_width": 800,
    "window_height": 600
  },
  "download": {
    "default_dir": "<home>/Downloads/YTDownloader",
    "default_quality": "1080p",
    "default_mode": "video",
    "concurrent_fragments": 4,
    "retries": 10,
    "merge_output_format": "mp4"
  },
  "cookies": {
    "source": "none",
    "browser": "chrome",
    "file_path": "data/cookies.txt"
  },
  "advanced": {
    "show_debug_logs": false,
    "sponsorblock_remove": false,
    "sponsorblock_categories": ["sponsor"]
  }
}
```

> **مهم:** لا يوجد قسم `audio.*` في المخطط الفعلي، ولا مفاتيح `download.embed_thumbnail`,
> `download.embed_metadata`, `download.write_subs`, `advanced.ffmpeg_location`,
> `advanced.js_runtime`, `advanced.node_path`, `advanced.use_nightly_yt_dlp`.
> هذه المفاتيح إن وُجدت في ملف `config.json` قديم تُهمَل (لا تُستخدم في الكود).

### 11.2 ConfigManager

```python
class ConfigManager:
    def __init__(self):
        self._data = self._load()          # data/config.json أو defaults

    def _load(self):
        if CONFIG_PATH.exists():
            return self._merge(self._defaults, json.load(CONFIG_PATH))
        return copy.deepcopy(_DEFAULTS)

    def _merge(self, base, override):      # دمج عميق — يحتفظ بالافتراضيات الناقصة
        ...

    def get(self, key_path, default=None)  # "download.default_quality"
    def set(self, key_path, value)         # + _save()
    def reset_to_defaults(self)
```

### 11.3 نوافذ الإعدادات (3 تبويبات)

| التبويب | الخيارات |
|---|---|
| **عام** | Theme (dark/light/system)، Language (ar/en)، مجلد الحفظ |
| **التحميل** | الجودة الافتراضية، الوضع الافتراضي (video/mp4_only/audio)، عدد الأجزاء المتزامنة، عدد المحاولات |
| **متقدم** | مصدر cookies (none/browser/file)، المتصفح، Debug logs، إزالة الرعايات (SponsorBlock) |

---

## 12. فحص التبعيات عند التشغيل

### 12.1 DependencyChecker (4 فحوصات)

```python
@dataclass
class DepResult:
    name: str; found: bool; path: str | None; version: str | None; required: bool

class DependencyChecker:
    BIN_DIR = Path(__file__).resolve().parent.parent / 'bin'

    def check_all(self):
        return [self._check_ffmpeg(), self._check_ffprobe(),
                self._check_node(), self._check_ytdlp()]

    def _check_ffmpeg(self):   # bin/ffmpeg.exe أو PATH → --version  (مطلوب)
    def _check_ffprobe(self):  # bin/ffprobe.exe أو PATH → --version (مطلوب)
    def _check_node(self):     # bin/node.exe أو PATH → --version   (اختياري)
    def _check_ytdlp(self):    # bin/yt-dlp.exe → --version          (مطلوب)
```

### 12.2 شاشة التشغيل (Startup Screen)

عند بدء التطبيق يظهر إطار مدمج في النافذة الرئيسية (`StartupCheckFrame`) يعرض:

```
✅ yt-dlp        <version>
✅ FFmpeg        <version>
✅ FFprobe       <version>
✅ Node.js       v<version>

[متابعة]   ← يُفعَّل فقط عند توفر كل التبعيات المطلوبة
```

في حالة وجود تبعية مفقودة (مطلوبة):

```
❌ FFmpeg        غير موجود — مطلوب لدمج الفيديو والصوت
[متابعة مفعّل تلقائياً بعد اكتمال كل الفحوصات المطلوبة]
```

---

## 13. معالجة الأخطاء

### 13.1 كتالوج الأخطاء (نتائج `_classify_error`)

| المعرّف | السبب | التصرف |
|---|---|---|
| `age_restricted` | المحتوى يتطلب تسجيل دخول (تحقق العمر) | تفعيل cookies من الإعدادات |
| `unavailable` | الفيديو محذوف أو خاص ("Video unavailable") | فحص الرابط أو تجربة فيديو آخر |
| `rate_limited` | طلبات كثيرة (HTTP 429) | الانتظار قبل إعادة المحاولة |
| رسالة cookies العربية | المتصفح مفتوح وقاعدة البيانات مقفلة | إغلاق المتصفح أو استخدام ملف cookies |
| `unsupported_url` | الرابط غير مدعوم (`UnsupportedError`) | فحص الرابط |
| `extractor:{msg}` | تغيّر في YouTube (خطأ استخراج) | تحديث yt-dlp / yt-dlp-ejs |
| `download_error:{msg}` | yt-dlp خرج بكود غير صفري | مراجعة الـ Logs |
| `unknown:{exc}` | تعذّر بدء العملية | مراجعة الاستثناء |
| `cancelled` | إلغاء المستخدم | — |

```python
def _classify_error(msg: str) -> str:
    low = msg.lower()
    if "sign in" in low or "age" in low:      return "age_restricted"
    if "unavailable" in low:                  return "unavailable"
    if "429" in low:                          return "rate_limited"
    if "cookie" in low or "could not copy":   return "فشل استخراج cookies من المتصفح — أغلق المتصفح أو استخدم ملف cookies في الإعدادات"
    if any(x in low for x in ("not supported", "unsupported", "no such extractor")):
        return "unsupported_url"
    if "error" in low:                        return f"extractor:{_strip_ytdlp_report_suffix(msg)}"
    return f"download_error:{msg}"
```

### 13.2 نمط معالجة الأخطاء

مع استخراج stdout يتم التقاط أول سطر `ERROR:` أثناء القراءة:
```python
if line.startswith("ERROR:"):
    if first_error is None:
        first_error = line[len("ERROR:"):].strip()
```
ثم بعد انتهاء العملية:
```python
rc = proc.wait()
if rc == 0 and first_error is None:
    return "ok"                                  # نجاح
msg = first_error or f"yt-dlp exited with code {rc}"
return _classify_error(msg)                      # تصنيف → event "error"
```

---

## 14. بنية المشروع

```
yt-downloader/
│
├── app.py                     ← Entry point (PATH + root CTk)
│
├── ui/
│   ├── __init__.py
│   ├── main_window.py         ← النافذة الرئيسية + لوحة الـ Playlist
│   ├── settings_dialog.py     ← نافذة الإعدادات (3 تبويبات)
│   ├── startup_check.py       ← فحص التبعيات عند التشغيل
│   ├── progress_widget.py     ← Progress bar + stats
│   ├── logs_panel.py          ← منطقة الـ logs
│   ├── playlist_panel.py      ← قائمة عناصر الـ Playlist + أزرار التنزيل
│   └── quality_selector.py    ← Dropdown الجودة + الوضع
│
├── core/
│   ├── __init__.py
│   ├── download_controller.py ← تحكم التحميل (subprocess) + threading + regex
│   ├── info_extractor.py      ← استخراج معلومات الفيديو (Python API)
│   ├── format_builder.py      ← بناء format strings + common opts
│   ├── dep_checker.py         ← فحص التبعيات (4 فحوصات)
│   └── config_manager.py      ← إدارة config.json
│
├── utils/
│   ├── __init__.py
│   ├── ui_logger.py           ← Logger → queue
│   ├── validators.py          ← التحقق من الروابط + تصنيف playlists
│   └── file_utils.py          ← مساعدات الملفات + أسماء مجلدات playlists
│
├── assets/
│   ├── logo.ico
│   ├── logo.png
│   └── fonts/
│
├── bin/                       ← Binaries (لا تُرفع على Git)
│   ├── ffmpeg.exe
│   ├── ffprobe.exe
│   ├── node.exe
│   └── yt-dlp.exe
│
├── data/                      ← ملفات Runtime
│   ├── config.json
│   └── cookies.txt            ← اختياري
│
├── requirements.txt
├── README.md
└── docx/                      ← PRD + مراجع التوثيق
```

> لا توجد مجلدات `downloads/` أو `logs/` ولا ملفا `history.json`/`archive.txt`
> ولا `build.spec` في الشجرة الحالية. المجلد الافتراضي للحفظ: `~/Downloads/YTDownloader`.

---

## 15. بناء الـ EXE

### 15.1 requirements.txt

```
yt-dlp[default]>=2025.1.1
yt-dlp-ejs>=0.8.0
customtkinter>=5.2.0
Pillow>=10.0.0
requests>=2.31.0
```

### 15.2 PyInstaller (مخطط — لم يُنفَّذ بعد)

لا يوجد `build.spec` في المستودع حالياً. التطبيق يعمل من المصدر:
```powershell
python app.py
```
الخطة المرسومة عند توثيق الـ packaging: PyInstaller `--onedir` بحيث تكون النتيجة `dist/YTDownloader/YTDownloader.exe` مع إدراج `bin/ffmpeg.exe` و `bin/ffprobe.exe` و `bin/node.exe` و `bin/yt-dlp.exe` و `assets/` في الحزمة.

> **لماذا `--onedir` وليس `--onefile`؟** أسرع في التشغيل (لا استخراج عند كل تشغيل) وأكثر توافقاً مع الفحوصات الأمنية.

---

## 16. الميزات المستقبلية

### المرحلة الثانية

| الميزة | الحالة | التفاصيل التقنية |
|---|---|---|
| **Playlist Download** | ✅ **مُنفَّذ** | `_playlist_worker` + `playlist_item`/`playlist_done` + `ui/playlist_panel.py` |
| **Thumbnail Preview** | ✅ **مُنفَّذ** | `extract_info(download=False)` → thumbnail (PIL) |
| **Video Info Panel** | ✅ **مُنفَّذ** | العنوان، القناة، المدة، الجودات |
| **Queue System** | 🚧 قائمة انتظار | `list[DownloadTask]` مع ThreadPool |
| **Subtitle Download** | 🚧 | `writesubtitles: True, subtitleslangs: ['ar', 'en']` |
| **Download History** | 🚧 | `history.json` بعد كل تحميل ناجح |
| **SponsorBlock** | ✅ **مُنفَّذ** (اختياري) | `sponsorblock_remove` في الإعدادات → `--sponsorblock-remove` |

### المرحلة الثالثة

| الميزة | التفاصيل التقنية |
|---|---|
| **Auto Update yt-dlp** | استبدال/تحديث `bin/yt-dlp.exe` تلقائياً |
| **Theme System** | customtkinter light/dark/system (متاح في الإعدادات) |
| **Multi-thread Downloads** | تحميلات متوازية متعددة |
| **Chapter Split** | `split_chapters: True` |
| **PyInstaller build.spec** | إضافة spec + script بناء |

---

## 17. قرارات معمارية — ADRs

### ADR-001: Subprocess للتحميل — Python API للاستخراج فقط (يُلغي ADR-001 في v2)

**القرار:** تنفيذ `bin/yt-dlp.exe` كـ subprocess للتحميل مع تحليل stdout، واستخدام `yt_dlp.YoutubeDL` بالـ Python API فقط لاستخراج المعلومات (`download=False`).

**السبب:**
- تحكم مباشر في العملية (`proc.terminate()`) عند الإلغاء
- فصل محرك التحميل عن نسخة الـ Python API → تحديث `yt-dlp.exe` مستقلاً
- أخطاء الـ extractor تعود كنص stdout يمكن تصنيفه بدقة (`_classify_error`)
- دمج الـ video+audio ومخرجاته النهائية يديرها yt-dlp بنفسه

**البديل المرفوض (في v2):** `YoutubeDL.download()` مباشرة — يربط المحرك بنسخة الـ pip agent.

> **تحديث:** قرر هذا ADR إبطال ADR-001 في `PRD_YTDownloader_v2.md`.

---

### ADR-002: Threading مع queue.Queue بدلاً من asyncio

**القرار:** `threading.Thread` + `queue.Queue` + `app.after()` polling.

**السبب:**
- tkinter/customtkinter ليس thread-safe لكنه safe مع `after()`
- yt-dlp نفسه يستخدم threads داخلياً — asyncio wrapper معقّد
- الـ pattern بسيط وسهل الـ debugging

---

### ADR-003: onedir بدلاً من onefile في PyInstaller (مخطط)

**القرار:** `--onedir` مع توزيع مجلد مضغوط (سيف يُنفَّذ لاحقاً).

**السبب:**
- أسرع في التشغيل
- أكثر توافقاً مع برامج الـ antivirus
- سهل تحديث ملف واحد (مثل `yt-dlp.exe`) بدون إعادة بناء

---

### ADR-004: إصدار yt-dlp عبر الملف الثنائي

**القرار:** يعتمد التطبيق على `bin/yt-dlp.exe` من releases الرسمية.

**السبب:**
- `yt-dlp[default]>=2025.1.1` في requirements يُستخدم للـ Python API (استخراج المعلومات)
- محرك التحميل ملف ثنائي مستقل يمكن تحديثه دون إعادة تشغيل بيئة Python
- YouTube يتغير بسرعة — تحديث `yt-dlp.exe` حل مباشر

---

### ADR-005: yt-dlp-ejs + Node.js لـ YouTube

**القرار:** تضمين `node.exe` في مجلد `bin/` وتمريره للـ CLI.

**السبب:**
- YouTube يستخدم JavaScript challenges لاستخراج الروابط
- `yt-dlp-ejs` هو الحل الرسمي بدلاً من حلول قديمة
- بدونه، بعض الفيديوهات تفشل أو تُحمَّل بجودة منخفضة

```python
opts['js_runtimes'] = {'node': {}}                      # → --js-runtimes node:<bin>/node.exe
opts['extractor_args'] = {'youtube-ejs': {}}            # → --extractor-args youtube-ejs
```

---

### ADR-006: format_sort لتفضيل H.264 على AV01

**القرار:** `format_sort: ['vcodec:h264,vp9,av01', 'res', 'br']`

**السبب:**
- yt-dlp افتراضياً يفضّل `av01 > vp9 > avc1`
- AV01 له توافق محدود مع المشغلات القديمة
- H.264 (avc1) يضمن أوسع توافق مع مشغلات الفيديو

**النتيجة:** `136+140` (avc1+m4a) بدلاً من `398+251` (av01+opus).

---

### ADR-007: Single-Root Architecture (CTk → CTkFrame)

**القرار:** نافذة `CTk` واحدة فقط، والمكونات (StartupCheck, MainWindow) `CTkFrame`.

**السبب:**
- إنشاء `CTk` متعددة يسبب تعارض `after` callbacks الداخلية
- `invalid command name` errors تظهر عند تدمير `CTk` مع `after` callbacks معلقة
- الحل: `StartupCheckFrame` و `MainWindow` يرثان من `CTkFrame` ويُدمجان في نفس `CTk` root

---

## 18. KPIs ومعايير النجاح

| المعيار | الهدف |
|---|---|
| وقت بدء التحميل | < 3 ثواني من الضغط على Download |
| معدل نجاح التحميل | > 95% للروابط الصالحة |
| استجابة الـ UI | لا تجميد في أي وقت |
| دعم 4K | يعمل مع فيديوهات 2160p على YouTube |
| دعم MP3/M4A | صوت نظيف مع metadata وthumbnail |
| دعم Playlists | تنزيل كامل أو انتقائي مع تحديث حالة كل عنصر |

---

## 19. نطاق المشروع

### داخل النطاق

- YouTube (فيديوهات، Shorts، Playlists)
- تحميل فيديو بجودة حتى 4K + MP4-only
- تحميل صوت MP3 / M4A
- واجهة GUI بـ customtkinter (عربي RTL / إنجليزي)
- دعم cookies (ملف + متصفح)
- SponsorBlock (اختياري)
- Windows 10/11 x64

### خارج النطاق حالياً

- مواقع أخرى (TikTok، Twitter، إلخ) — yt-dlp يدعمها لكن الـ UI لا
- Android / iOS
- Cloud backend أو حسابات مستخدمين
- Browser extension
- Live stream recording

---

*آخر تحديث: سبتمبر 2026 — ReizanTech*

---

## سجل التغييرات

| التاريخ | التغيير |
|---|---|
| مايو 2026 | **v2.0** — الإصدار الأولي من PRD (مستند تاريخي) |
| مايو 2026 | **تعديلات v2:** `format_sort`، `throttledratelimit`، `yt-dlp-ejs`، Single-Root، cookies `none` |
| سبتمبر 2026 | **v3.0** — تصحيح المحاور الرئيسية حسب التنفيذ الفعلي: محرك التحميل **subprocess `bin/yt-dlp.exe`** بدلاً من Python API، مخطط config الفعلي من `_DEFAULTS`، 3 تبويبات إعدادات، تحميل Playlists مُنفَّذ، 4 فحوصات تبعيات، كتالوج أخطاء `_classify_error`، إزالة الملفات غير الموجودة (build.spec/history/archive)، SponsorBlock في النطاق |