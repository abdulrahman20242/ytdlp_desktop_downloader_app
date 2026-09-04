# PRD — YT Downloader Desktop Application
### Version 2.0 | ReizanTech | May 2026

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
10. [نظام الـ Progress Hook](#10-نظام-الـ-progress-hook)
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

**YT Downloader** تطبيق Desktop يعمل على Windows، مبني بـ Python مع واجهة `customtkinter`، يتيح تحميل الفيديوهات والصوت من YouTube بكفاءة عالية.

التطبيق يستخدم `yt-dlp` عبر **Python API مباشرة** (لا subprocess)، مما يوفر تحكماً كاملاً في التحميل، ومعالجة دقيقة للأخطاء، وعرضاً لحظياً لتقدم التحميل.

---

## 2. الهدف والمشكلة

### المشكلة
لا يوجد تطبيق Desktop بسيط وموثوق يدعم YouTube الحديث (n-sig challenges، age-restricted content) مع واجهة عربية/إنجليزية واضحة.

### الهدف
تقديم تجربة تحميل سلسة تدعم:
- أعلى جودة متاحة (حتى 4K)
- تحويل صوت بكودك احترافي (MP3 / M4A)
- تحميل Playlists بالكامل
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
| Downloader | yt-dlp | nightly | `pip install --pre yt-dlp[default]` |
| Media Processing | FFmpeg + FFprobe | 7.x+ | من yt-dlp/FFmpeg-Builds |
| JS Support | yt-dlp-ejs + Node.js | Node 20 LTS | لحل YouTube n-sig |
| Packaging | PyInstaller | 6.x | `--onedir` (لا `--onefile`) |

> **ملاحظة حول `--onefile` vs `--onedir`:** `--onedir` أسرع في التشغيل ويتجنب مشاكل antivirus مع الملفات المؤقتة التي يستخرجها `--onefile`.

> **ملاحظة حول yt-dlp channel:** استخدام `nightly` channel بدلاً من `stable` لأن YouTube يتغير بسرعة وـ `stable` تتأخر في إصلاح المستخرجات.

---

## 5. متطلبات النظام

### 5.1 بيئة التشغيل
- Windows 10 / 11 (x64)
- Python 3.11+
- Node.js 20 LTS (مطلوب لـ YouTube)
- FFmpeg + FFprobe (حزمة واحدة)

### 5.2 ملفات الـ Binaries

```
project/
├── bin/
│   ├── yt-dlp.exe         ← من releases الرسمية (نفس المثبّت pip)
│   ├── ffmpeg.exe         ← من yt-dlp/FFmpeg-Builds
│   ├── ffprobe.exe        ← نفس المصدر
│   └── node.exe           ← Node.js standalone binary
```

> **ملاحظة:** التطبيق يستخدم `yt-dlp` كـ Python library مباشرة (لا يحتاج `yt-dlp.exe` إلا عند التحديث التلقائي). أما `ffmpeg.exe` و`node.exe` فمطلوبان دائماً لأن yt-dlp ينفذهما كـ subprocess داخلياً.

### 5.3 الملفات الاختيارية

```
project/
└── data/
    └── cookies.txt        ← اختياري، للمحتوى المقيّد
```

---

## 6. المعمارية الهندسية

```
┌─────────────────────────────────────────────────────┐
│                    UI Layer                          │
│  customtkinter · MainWindow · SettingsDialog         │
│  ProgressWidget · LogsPanel · QualitySelector        │
└────────────────────┬────────────────────────────────┘
                     │  events / callbacks
┌────────────────────▼────────────────────────────────┐
│                Controller Layer                      │
│  DownloadController · ValidationService              │
│  ConfigManager · DependencyChecker                   │
└──────┬─────────────────────┬──────────────────────── ┘
       │                     │
┌──────▼──────┐    ┌─────────▼─────────┐
│  Download   │    │   Info Extractor  │
│  Engine     │    │   (no download)   │
│  yt-dlp API │    │   yt-dlp API      │
└──────┬──────┘    └─────────┬─────────┘
       │                     │
┌──────▼──────────────────────▼────────┐
│           yt_dlp.YoutubeDL           │
│  progress_hooks · postprocessors     │
│  logger · match_filter               │
└──────┬───────────────────────────────┘
       │  spawns external processes
┌──────▼──────────────────────────────┐
│  bin/ffmpeg.exe   bin/node.exe      │
└─────────────────────────────────────┘
```

### 6.1 القاعدة المحورية: Python API لا Subprocess

```python
# ✅ الطريقة الصحيحة — Python API
from yt_dlp import YoutubeDL

ydl_opts = {
    'format': 'bv*[height<=1080]+ba/b[height<=1080]',
    'outtmpl': '%(title)s [%(id)s].%(ext)s',
    'ffmpeg_location': './bin',
    'progress_hooks': [self._on_progress],
    'logger': self._logger,
}
with YoutubeDL(ydl_opts) as ydl:
    ydl.download([url])

# ❌ الطريقة الخاطئة — subprocess يعطي تحكماً أقل
import subprocess
subprocess.run(['yt-dlp.exe', url])
```

---

## 7. نموذج الـ Threading

**المشكلة الأساسية:** yt-dlp blocking operation — لو اشتغل في Main Thread سيجمّد الـ GUI.

**الحل:** كل عملية تحميل تشتغل في `threading.Thread` منفصل، والتواصل مع الـ GUI يكون عبر `queue.Queue`.

```python
import threading
import queue

class DownloadController:
    def __init__(self):
        self._queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start_download(self, url: str, opts: dict):
        """يبدأ التحميل في thread منفصل"""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._download_worker,
            args=(url, opts),
            daemon=True
        )
        self._thread.start()
        # UI loop يستقرئ الـ queue كل 100ms
        self._poll_queue()

    def _download_worker(self, url: str, opts: dict):
        opts['progress_hooks'] = [self._progress_hook]
        opts['logger'] = self._logger
        try:
            with YoutubeDL(opts) as ydl:
                ydl.download([url])
            self._queue.put(('done', None))
        except Exception as e:
            self._queue.put(('error', str(e)))

    def _progress_hook(self, d: dict):
        """يُستدعى من download thread، يضع البيانات في queue"""
        self._queue.put(('progress', d))

    def _poll_queue(self):
        """يعمل في Main Thread — آمن لتحديث الـ GUI"""
        try:
            while True:
                event, data = self._queue.get_nowait()
                if event == 'progress':
                    self._update_ui_progress(data)
                elif event == 'done':
                    self._on_success()
                    return
                elif event == 'error':
                    self._on_error(data)
                    return
        except queue.Empty:
            pass
        # جدولة الاستقراء التالي بعد 100ms
        app.after(100, self._poll_queue)

    def cancel(self):
        self._stop_event.set()
```

---

## 8. الميزات الأساسية MVP

### 8.1 تحميل فيديو

**تدفق الاستخدام:**
1. المستخدم يلصق الرابط
2. التطبيق يتحقق من صحة الرابط (regex بسيط + استخراج أولي)
3. يتم استخراج معلومات الفيديو (`download=False`) وعرض العنوان والصورة المصغرة
4. المستخدم يختار الجودة والصيغة
5. يضغط Download
6. Progress Bar يتحدث لحظياً
7. بعد الانتهاء: إشعار نجاح + زر فتح المجلد

**yt-dlp opts للفيديو:**
```python
{
    'format': FORMAT_MAP[quality][mode],   # انظر القسم 9
    'merge_output_format': 'mp4',
    'outtmpl': str(save_dir / '%(title)s [%(id)s].%(ext)s'),
    'ffmpeg_location': str(BIN_DIR),
    'concurrent_fragments': 4,             # تسريع HLS/DASH
    'retries': 10,
    'fragment_retries': 10,
    'ignoreerrors': False,
}
```

---

### 8.2 تحميل MP3

```python
{
    'format': 'm4a/bestaudio/best',
    'outtmpl': str(save_dir / '%(title)s [%(id)s].%(ext)s'),
    'ffmpeg_location': str(BIN_DIR),
    'postprocessors': [
        {
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',    # kbps
        },
        {
            'key': 'FFmpegMetadata',
            'add_metadata': True,
        },
        {
            'key': 'EmbedThumbnail',
        },
    ],
    'writethumbnail': True,
}
```

> **ملاحظة:** تضمين الـ thumbnail في ملف MP3 يتطلب كلاً من `writethumbnail: True` و`EmbedThumbnail` postprocessor. بدون `ffmpeg_location` صريح، yt-dlp قد لا يجد ffmpeg.

---

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

---

### 8.4 اختيار مجلد الحفظ

```python
import tkinter.filedialog as fd

save_dir = fd.askdirectory(
    title='اختر مجلد الحفظ',
    initialdir=config.get('default_download_dir', Path.home() / 'Downloads')
)
```

الاختيار يُحفظ في `config.json` ويُستخدم كقيمة افتراضية في الجلسات التالية.

---

### 8.5 Progress Bar

يعتمد على `progress_hooks` من yt-dlp:

```python
def _on_progress(d: dict):
    if d['status'] == 'downloading':
        percent = float(d.get('_percent_str', '0%').strip('%'))
        speed   = d.get('_speed_str', 'N/A')
        eta     = d.get('_eta_str', 'N/A')
        # → تحديث UI
    elif d['status'] == 'finished':
        # الملف جاهز، ينتظر post-processing
        pass
    elif d['status'] == 'error':
        # خطأ في fragment
        pass
```

عناصر الـ Progress Widget:
- `CTkProgressBar` — نسبة مئوية (0.0 → 1.0)
- Label: `45.3% · 2.3 MB/s · ETA 00:32`
- Label: اسم الملف المُحمَّل حالياً

---

### 8.6 Logs Panel

نافذة `CTkTextbox` قابلة للطي، تعرض:
- رسائل yt-dlp (debug / info / warning / error)
- أحداث التحميل (بدء، دمج، اكتمال)
- الأخطاء مع اقتراحات الحل

```python
class UILogger:
    """Logger مخصص يوجّه مخرجات yt-dlp إلى الـ queue"""
    def __init__(self, queue: queue.Queue):
        self._q = queue

    def debug(self, msg):
        if not msg.startswith('[debug] '):
            self._q.put(('log', f'[INFO] {msg}'))

    def warning(self, msg):
        self._q.put(('log', f'[WARN] {msg}'))

    def error(self, msg):
        self._q.put(('log', f'[ERROR] {msg}'))
```

---

### 8.7 دعم Cookies

**خيار 1 — ملف cookies.txt:**
```python
if Path('data/cookies.txt').exists():
    opts['cookiefile'] = 'data/cookies.txt'
```

**خيار 2 — استيراد من المتصفح مباشرة (أوصى به):**
```python
opts['cookiesfrombrowser'] = ('chrome',)  # أو 'firefox', 'edge'
```

الواجهة تعرض Dropdown لاختيار المتصفح أو تحديد ملف يدوياً.

---

## 9. منطق اختيار الصيغة

### 9.1 جدول الـ Format Strings الكاملة

| الجودة | وضع فيديو | وضع MP4 only | وضع صوت فقط |
|---|---|---|---|
| Best (Auto) | `bv*+ba/b` | `bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b` | `bestaudio/best` |
| 4K (2160p) | `bv*[height<=2160]+ba/b[height<=2160]` | `bv[height<=2160][ext=mp4]+ba[ext=m4a]/b[height<=2160]` | — |
| 1440p | `bv*[height<=1440]+ba/b[height<=1440]` | `bv[height<=1440][ext=mp4]+ba[ext=m4a]/b[height<=1440]` | — |
| 1080p | `bv*[height<=1080]+ba/b[height<=1080]` | `bv[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]` | — |
| 720p | `bv*[height<=720]+ba/b[height<=720]` | `bv[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]` | — |
| 480p | `bv*[height<=480]+ba/b[height<=480]` | — | — |
| 360p | `bv*[height<=360]+ba/b[height<=360]` | — | — |

```python
FORMAT_MAP = {
    'best':   'bv*+ba/b',
    '2160p':  'bv*[height<=2160]+ba/b[height<=2160]',
    '1440p':  'bv*[height<=1440]+ba/b[height<=1440]',
    '1080p':  'bv*[height<=1080]+ba/b[height<=1080]',
    '720p':   'bv*[height<=720]+ba/b[height<=720]',
    '480p':   'bv*[height<=480]+ba/b[height<=480]',
    '360p':   'bv*[height<=360]+ba/b[height<=360]',
    '240p':   'bv*[height<=240]+ba/b[height<=240]',
    'mp3':    'm4a/bestaudio/best',  # مع postprocessor
    'm4a':    'm4a/bestaudio/best',
}
```

### 9.2 فحص الجودات المتاحة قبل التحميل

```python
def get_available_qualities(url: str) -> list[str]:
    """يستخرج الجودات الفعلية المتاحة للفيديو"""
    opts = {'quiet': True, 'ffmpeg_location': str(BIN_DIR)}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        info = ydl.sanitize_info(info)

    heights = set()
    for fmt in info.get('formats', []):
        h = fmt.get('height')
        if h:
            heights.add(h)

    # إرجاع قائمة منقّاة ومرتبة
    thresholds = [2160, 1440, 1080, 720, 480, 360, 240]
    return [f'{h}p' for h in thresholds if any(x >= h for x in heights)]
```

---

## 10. نظام الـ Progress Hook

### 10.1 هيكل بيانات الـ hook

```python
# d['status'] == 'downloading'
{
    'status':           'downloading',
    'filename':         'video.mp4',
    'downloaded_bytes': 15728640,      # bytes محمَّلة
    'total_bytes':      104857600,     # إجمالي (قد يكون None)
    'total_bytes_estimate': 95000000,  # تقدير إن لم يكن معروفاً
    '_percent_str':     ' 15.0%',
    '_speed_str':       '2.50MiB/s',
    '_eta_str':         '00:35',
    '_elapsed_str':     '00:06',
    'speed':            2621440.0,     # bytes/sec
    'eta':              35,            # ثانية
}

# d['status'] == 'finished'
{
    'status':    'finished',
    'filename':  'video.f137.mp4',    # fragment file, قبل الدمج
    'total_bytes': 104857600,
}
```

### 10.2 حساب نسبة التقدم بشكل آمن

```python
def _safe_percent(d: dict) -> float:
    total = d.get('total_bytes') or d.get('total_bytes_estimate')
    downloaded = d.get('downloaded_bytes', 0)
    if total:
        return min(downloaded / total, 1.0)
    # fallback: parse string
    raw = d.get('_percent_str', '0%').strip().rstrip('%')
    try:
        return float(raw) / 100
    except ValueError:
        return 0.0
```

---

## 11. الإعدادات — config.json

### 11.1 المخطط الكامل

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
    "default_dir": "C:/Users/User/Downloads/YTDownloader",
    "default_quality": "1080p",
    "default_mode": "video",
    "concurrent_fragments": 4,
    "retries": 10,
    "merge_output_format": "mp4",
    "embed_thumbnail": false,
    "embed_metadata": true,
    "write_subs": false,
    "sub_langs": "ar,en"
  },
  "audio": {
    "default_format": "mp3",
    "mp3_quality": "192",
    "embed_thumbnail": true
  },
  "cookies": {
    "source": "file",
    "browser": "chrome",
    "file_path": "data/cookies.txt"
  },
  "advanced": {
    "ffmpeg_location": "bin",
    "js_runtime": "node",
    "node_path": "bin/node.exe",
    "use_nightly_yt_dlp": true,
    "show_debug_logs": false,
    "sponsorblock_remove": false,
    "sponsorblock_categories": ["sponsor"]
  }
}
```

### 11.2 ConfigManager

```python
import json
from pathlib import Path

CONFIG_PATH = Path('data/config.json')

class ConfigManager:
    _defaults = { ... }  # القيم الافتراضية أعلاه

    def __init__(self):
        self._data = self._load()

    def _load(self) -> dict:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, encoding='utf-8') as f:
                saved = json.load(f)
            return self._merge(self._defaults, saved)
        return self._defaults.copy()

    def _merge(self, base: dict, override: dict) -> dict:
        """دمج عميق — يحتفظ بالقيم الافتراضية للمفاتيح الناقصة"""
        result = base.copy()
        for k, v in override.items():
            if isinstance(v, dict) and k in result:
                result[k] = self._merge(result[k], v)
            else:
                result[k] = v
        return result

    def get(self, key_path: str, default=None):
        """مثال: config.get('download.default_quality')"""
        keys = key_path.split('.')
        obj = self._data
        for k in keys:
            obj = obj.get(k) if isinstance(obj, dict) else None
        return obj if obj is not None else default

    def set(self, key_path: str, value):
        keys = key_path.split('.')
        obj = self._data
        for k in keys[:-1]:
            obj = obj.setdefault(k, {})
        obj[keys[-1]] = value
        self._save()

    def _save(self):
        CONFIG_PATH.parent.mkdir(exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
```

---

## 12. فحص التبعيات عند التشغيل

### 12.1 DependencyChecker

```python
import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass

@dataclass
class DepResult:
    name: str
    found: bool
    path: str | None
    version: str | None
    required: bool

class DependencyChecker:
    BIN_DIR = Path('bin')

    def check_all(self) -> list[DepResult]:
        return [
            self._check_ffmpeg(),
            self._check_node(),
            self._check_ytdlp(),
        ]

    def _check_ffmpeg(self) -> DepResult:
        path = self.BIN_DIR / 'ffmpeg.exe'
        if not path.exists():
            path = shutil.which('ffmpeg')
        if path:
            try:
                out = subprocess.check_output(
                    [str(path), '-version'], stderr=subprocess.STDOUT, text=True
                )
                version = out.split('\n')[0]
            except Exception:
                version = 'unknown'
            return DepResult('FFmpeg', True, str(path), version, required=True)
        return DepResult('FFmpeg', False, None, None, required=True)

    def _check_node(self) -> DepResult:
        path = self.BIN_DIR / 'node.exe'
        if not path.exists():
            path = shutil.which('node')
        if path:
            try:
                ver = subprocess.check_output(
                    [str(path), '--version'], text=True
                ).strip()
            except Exception:
                ver = 'unknown'
            return DepResult('Node.js', True, str(path), ver, required=True)
        return DepResult('Node.js', False, None, None, required=True)

    def _check_ytdlp(self) -> DepResult:
        try:
            import yt_dlp
            return DepResult('yt-dlp', True, yt_dlp.__file__, yt_dlp.version.__version__, required=True)
        except ImportError:
            return DepResult('yt-dlp', False, None, None, required=True)
```

### 12.2 شاشة التشغيل (Startup Screen)

عند بدء التطبيق يظهر Dialog صغير يعرض:

```
✅ yt-dlp        2025.05.01-nightly
✅ FFmpeg        7.1.1
✅ Node.js       v20.14.0

[Continue]
```

في حالة وجود تبعية مفقودة:

```
✅ yt-dlp        2025.05.01-nightly
❌ FFmpeg        غير موجود — مطلوب لدمج الفيديو والصوت
⚠️ Node.js       غير موجود — بعض فيديوهات YouTube لن تعمل

[تعليمات التثبيت]   [تجاهل (غير مُوصى به)]
```

---

## 13. معالجة الأخطاء

### 13.1 كتالوج الأخطاء

| الخطأ | السبب | الرسالة للمستخدم | الحل التقني |
|---|---|---|---|
| `Video unavailable` | الفيديو محذوف أو خاص | "الفيديو غير متاح أو محذوف" | عرض رسالة، لا retry |
| `Sign in to confirm age` | محتوى مقيّد بالعمر | "يتطلب تسجيل دخول — استخدم cookies" | توجيه لإعداد cookies |
| `HTTP Error 429` | Rate limiting | "الطلبات كثيرة — يُعاد المحاولة..." | retry مع exponential backoff |
| `ffmpeg not found` | ffmpeg مفقود | "FFmpeg مطلوب لدمج الفيديو" | رابط التثبيت |
| `no such format` | الجودة المطلوبة غير متاحة | "جودة {X} غير متاحة، جرّب جودة أقل" | fallback تلقائي |
| `Network error` | انقطاع الإنترنت | "خطأ في الشبكة" | retry button |
| `ExtractorError` | تغيير في YouTube | "خطأ في استخراج الفيديو — حدّث yt-dlp" | زر تحديث yt-dlp |
| `UnsupportedError` | رابط غير مدعوم | "هذا الرابط غير مدعوم" | عرض المواقع المدعومة |

### 13.2 نمط معالجة الأخطاء

```python
from yt_dlp.utils import (
    DownloadError,
    ExtractorError,
    UnsupportedError,
    GeoRestrictedError,
)

def _download_worker(self, url, opts):
    try:
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
        self._queue.put(('done', None))

    except DownloadError as e:
        msg = str(e)
        if 'Sign in' in msg or 'age' in msg.lower():
            self._queue.put(('error', 'age_restricted'))
        elif 'unavailable' in msg.lower():
            self._queue.put(('error', 'unavailable'))
        elif '429' in msg:
            self._queue.put(('error', 'rate_limited'))
        else:
            self._queue.put(('error', f'download_error:{msg}'))

    except ExtractorError as e:
        self._queue.put(('error', f'extractor:{e}'))

    except UnsupportedError:
        self._queue.put(('error', 'unsupported_url'))

    except Exception as e:
        self._queue.put(('error', f'unknown:{e}'))
```

---

## 14. بنية المشروع

```
yt-downloader/
│
├── app.py                     ← Entry point
│
├── ui/
│   ├── __init__.py
│   ├── main_window.py         ← النافذة الرئيسية
│   ├── settings_dialog.py     ← نافذة الإعدادات
│   ├── startup_check.py       ← فحص التبعيات عند التشغيل
│   ├── progress_widget.py     ← Progress bar + stats
│   ├── logs_panel.py          ← منطقة الـ logs
│   └── quality_selector.py   ← Dropdown الجودة
│
├── core/
│   ├── __init__.py
│   ├── download_controller.py ← التحكم في التحميل + threading
│   ├── info_extractor.py      ← استخراج معلومات الفيديو
│   ├── format_builder.py      ← بناء format strings
│   ├── dep_checker.py         ← فحص التبعيات
│   └── config_manager.py      ← إدارة config.json
│
├── utils/
│   ├── __init__.py
│   ├── ui_logger.py           ← Logger → queue
│   ├── validators.py          ← التحقق من الروابط
│   └── file_utils.py          ← مساعدات الملفات
│
├── assets/
│   ├── logo.ico
│   ├── logo.png
│   └── fonts/
│
├── bin/                       ← Binaries (لا تُرفع على Git)
│   ├── ffmpeg.exe
│   ├── ffprobe.exe
│   └── node.exe
│
├── data/                      ← ملفات Runtime
│   ├── config.json
│   ├── history.json
│   ├── archive.txt            ← yt-dlp download archive
│   └── cookies.txt            ← اختياري
│
├── downloads/                 ← المجلد الافتراضي للتحميل
│
├── logs/
│   └── app.log
│
├── build.spec                 ← PyInstaller spec file
├── requirements.txt
└── README.md
```

---

## 15. بناء الـ EXE

### 15.1 requirements.txt

```
yt-dlp[default]>=2025.1.1
customtkinter>=5.2.0
Pillow>=10.0.0
requests>=2.31.0
```

### 15.2 PyInstaller Spec (الكاملة)

```python
# build.spec
import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[
        ('bin/ffmpeg.exe',  'bin'),
        ('bin/ffprobe.exe', 'bin'),
        ('bin/node.exe',    'bin'),
    ],
    datas=[
        ('assets',     'assets'),
        ('ui',         'ui'),
        ('core',       'core'),
    ],
    hiddenimports=[
        'yt_dlp',
        'yt_dlp.extractor',
        'yt_dlp.extractor.youtube',
        'yt_dlp.postprocessor',
        'customtkinter',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,    # --onedir
    name='YTDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,            # بدون console window
    icon='assets/logo.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='YTDownloader',
)
```

```powershell
# بناء التطبيق
pyinstaller build.spec --clean

# النتيجة في: dist/YTDownloader/YTDownloader.exe
```

> **لماذا `--onedir` وليس `--onefile`؟**
> - `--onefile` يستخرج الملفات لـ temp folder عند كل تشغيل → بطيء جداً
> - بعض برامج الـ antivirus تحذف الملفات المؤقتة
> - `--onedir` يعطي مجلداً واحداً قابلاً للـ zip والتوزيع

---

## 16. الميزات المستقبلية

### المرحلة الثانية

| الميزة | التفاصيل التقنية |
|---|---|
| **Playlist Download** | `yt-dlp` يدعمه افتراضياً، نضيف `--yes-playlist` وعداداً للفيديوهات |
| **Queue System** | قائمة انتظار بـ `list[DownloadTask]` مع threading pool |
| **Thumbnail Preview** | `extract_info(download=False)` → `info['thumbnail']` → `requests.get` → PIL |
| **Video Info Panel** | نفس `extract_info` → عرض العنوان، القناة، المدة، الجودات |
| **Subtitle Download** | `writesubtitles: True, subtitleslangs: ['ar', 'en']` |
| **Download History** | `history.json` يُحدَّث بعد كل تحميل ناجح |
| **SponsorBlock** | `sponsorblock_remove: ['sponsor', 'intro']` في opts |

### المرحلة الثالثة

| الميزة | التفاصيل التقنية |
|---|---|
| **Auto Update yt-dlp** | `subprocess.run(['pip', 'install', '--pre', '--upgrade', 'yt-dlp[default]'])` |
| **Theme System** | customtkinter يدعم light/dark/system |
| **Multi-thread Downloads** | `concurrent_fragments: N` موجود، نضيف downloads متوازية |
| **Chapter Split** | `split_chapters: True` + `download_sections: '*'` |

---

## 17. قرارات معمارية — ADRs

### ADR-001: Python API بدلاً من subprocess

**القرار:** استخدام `from yt_dlp import YoutubeDL` مباشرة.

**السبب:**
- تحكم كامل في `progress_hooks` و`logger`
- معالجة استثناءات Python بدلاً من تحليل نص
- لا overhead لعملية subprocess منفصلة
- سهولة اختبار الـ unit tests

**البديل المرفوض:** `subprocess.run(['yt-dlp.exe', ...])` — صعب التحكم وهش.

---

### ADR-002: Threading مع queue.Queue بدلاً من asyncio

**القرار:** `threading.Thread` + `queue.Queue` + `app.after()` polling.

**السبب:**
- tkinter/customtkinter ليس thread-safe لكنه safe مع `after()`
- yt-dlp نفسه يستخدم threads داخلياً — asyncio wrapper معقّد
- الـ pattern بسيط وسهل الـ debugging

**البديل المرفوض:** asyncio — يتطلب wrapper كامل لـ yt-dlp ومعقّد مع tkinter.

---

### ADR-003: onedir بدلاً من onefile في PyInstaller

**القرار:** `--onedir` مع توزيع مجلد مضغوط.

**السبب:**
- أسرع في التشغيل (لا استخراج عند كل تشغيل)
- أكثر توافقاً مع برامج الـ antivirus
- سهل تحديث ملف واحد (مثل `yt-dlp.exe`) بدون إعادة بناء

---

### ADR-004: نسخة nightly من yt-dlp

**القرار:** `pip install --pre "yt-dlp[default]"` (nightly channel).

**السبب:**
- YouTube يتغير بسرعة و`stable` تتأخر شهراً أو أكثر في الإصلاحات
- `nightly` هو الـ recommended channel للمستخدمين العاديين حسب الـ README الرسمي

---

### ADR-005: yt-dlp-ejs + Node.js لـ YouTube

**القرار:** تضمين `node.exe` في مجلد `bin/` وتمريره عبر `extractor_args`.

**السبب:**
- YouTube يستخدم JavaScript challenges لاستخراج الروابط
- `yt-dlp-ejs` هو الحل الرسمي بدلاً من حلول قديمة
- بدونه، بعض الفيديوهات تفشل أو تُحمَّل بجودة منخفضة

```python
opts['extractor_args'] = {
    'youtube': {
        'player_client': ['android_vr', 'web_safari']
    }
}
```

---

## 18. KPIs ومعايير النجاح

| المعيار | الهدف |
|---|---|
| وقت بدء التحميل | < 3 ثواني من الضغط على Download |
| معدل نجاح التحميل | > 95% للروابط الصالحة |
| استهلاك الـ CPU أثناء التحميل | < 20% (التحميل I/O-bound لا CPU-bound) |
| استجابة الـ UI | لا تجميد في أي وقت |
| دعم 4K | يعمل مع فيديوهات 2160p على YouTube |
| دعم MP3/M4A | صوت نظيف مع metadata وthumbnail |
| حجم الـ EXE النهائي | < 150 MB (مع ffmpeg وnode) |

---

## 19. نطاق المشروع

### داخل النطاق

- YouTube (فيديوهات، Shorts، Playlists، Channels)
- تحميل فيديو بجودة حتى 4K
- تحميل صوت MP3 / M4A
- واجهة GUI بـ customtkinter
- دعم cookies (ملف + متصفح)
- تحويل EXE بـ PyInstaller
- Windows 10/11 x64

### خارج النطاق حالياً

- مواقع أخرى (TikTok، Twitter، إلخ) — yt-dlp يدعمها لكن الـ UI لا
- Android / iOS
- Cloud backend أو حسابات مستخدمين
- Browser extension
- Live stream recording

---

*آخر تحديث: مايو 2026 — ReizanTech*
