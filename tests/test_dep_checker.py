import subprocess

import pytest

from core.dep_checker import DependencyChecker, DepResult


@pytest.fixture
def checker(tmp_path):
    c = DependencyChecker()
    c.BIN_DIR = tmp_path / "bin"
    c.BIN_DIR.mkdir(exist_ok=True)
    return c


@pytest.fixture
def no_which(monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda _name: None)


def test_exe_in_bin_dir_reports_found(checker, monkeypatch):
    exe = checker.BIN_DIR / "ffmpeg.exe"
    exe.write_text("fake", encoding="utf-8")

    def fake_output(cmd, **kwargs):
        return "ffmpeg version 6.0-full\ncopyright ..."

    monkeypatch.setattr(subprocess, "check_output", fake_output)

    result = checker._check_ffmpeg()
    assert result.found is True
    assert result.name == "FFmpeg"
    assert result.path == str(exe)
    assert "ffmpeg version 6.0" in result.version
    assert result.required is True


def test_exe_missing_and_not_on_path_reports_missing(checker, no_which):
    result = checker._check_ffmpeg()
    assert result.found is False
    assert result.path is None
    assert result.version is None
    assert result.required is True


def test_bin_dir_missing_but_exe_on_path_reports_found_with_version(
    checker, monkeypatch
):
    import shutil

    monkeypatch.setattr(
        shutil, "which", lambda name: "C:\\ffmpeg\\ffmpeg.exe" if name == "ffmpeg" else None
    )

    def fake_output(cmd, **kwargs):
        return "ffmpeg version 7.0"

    monkeypatch.setattr(subprocess, "check_output", fake_output)

    result = checker._check_ffmpeg()
    assert result.found is True
    assert result.path == "C:\\ffmpeg\\ffmpeg.exe"
    assert result.version == "ffmpeg version 7.0"


def test_ffprobe_missing_reports_required(checker, no_which):
    result = checker._check_ffprobe()
    assert result.found is False
    assert result.required is True
    assert result.name == "FFprobe"


def test_node_missing_reports_optional(checker, no_which):
    result = checker._check_node()
    assert result.found is False
    assert result.required is False
    assert result.name == "Node.js"


def test_node_present_reports_version(checker, monkeypatch):
    exe = checker.BIN_DIR / "node.exe"
    exe.write_text("fake", encoding="utf-8")

    def fake_output(cmd, **kwargs):
        return "v22.11.0"

    monkeypatch.setattr(subprocess, "check_output", lambda cmd, **kwargs: "v22.11.0\n")

    result = checker._check_node()
    assert result.found is True
    assert result.version == "v22.11.0"
    assert result.required is False


def test_ytdlp_python_package_exists_but_bundled_exe_missing(checker):
    # Python yt_dlp exists, but bundled bin/yt-dlp.exe is missing
    result = checker._check_ytdlp()
    assert result.found is False
    assert result.required is True
    assert result.path is None

    py_result = checker._check_ytdlp_python()
    assert py_result.found is True
    assert py_result.required is True
    assert py_result.version is not None


def test_ytdlp_bundled_exe_exits_nonzero(checker, monkeypatch):
    exe = checker.BIN_DIR / "yt-dlp.exe"
    exe.write_text("fake", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="crash")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = checker._check_ytdlp()
    assert result.found is False
    assert result.required is True


def test_ytdlp_bundled_exe_raises_execution_error(checker, monkeypatch):
    exe = checker.BIN_DIR / "yt-dlp.exe"
    exe.write_text("fake", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        raise OSError("cannot execute")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = checker._check_ytdlp()
    assert result.found is False
    assert result.required is True


def test_ytdlp_bundled_exe_succeeds(checker, monkeypatch):
    exe = checker.BIN_DIR / "yt-dlp.exe"
    exe.write_text("fake", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="2026.08.19\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = checker._check_ytdlp()
    assert result.found is True
    assert result.required is True
    assert result.version == "2026.08.19"
    assert result.path == str(exe)


def test_ytdlp_python_missing_reports_required(checker, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "yt_dlp":
            raise ImportError("no yt_dlp")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = checker._check_ytdlp_python()
    assert result.found is False
    assert result.required is True
    assert result.path is None


def test_subprocess_failure_reports_unknown_version(checker, monkeypatch):
    exe = checker.BIN_DIR / "ffmpeg.exe"
    exe.write_text("fake", encoding="utf-8")

    def boom(cmd, **kwargs):
        raise OSError("cannot run")

    monkeypatch.setattr(subprocess, "check_output", boom)

    result = checker._check_ffmpeg()
    assert result.found is True
    assert result.version == "unknown"


def test_ffprobe_present_reports_version(checker, monkeypatch):
    exe = checker.BIN_DIR / "ffprobe.exe"
    exe.write_text("fake", encoding="utf-8")

    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda cmd, **kwargs: "ffprobe version 6.0-full\n...",
    )

    result = checker._check_ffprobe()
    assert result.found is True
    assert result.path == str(exe)
    assert result.version.startswith("ffprobe version 6.0")
    assert result.required is True


def test_node_subprocess_failure_reports_unknown_version(checker, monkeypatch):
    exe = checker.BIN_DIR / "node.exe"
    exe.write_text("fake", encoding="utf-8")

    def boom(cmd, **kwargs):
        raise OSError("cannot run node")

    monkeypatch.setattr(subprocess, "check_output", boom)

    result = checker._check_node()
    assert result.found is True
    assert result.version == "unknown"
    assert result.required is False


def test_check_all_returns_five_results(checker, no_which, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "yt_dlp":
            raise ImportError("no yt_dlp")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    results = checker.check_all()
    # 5 base results, no mismatch entry because neither yt-dlp is found
    assert len(results) == 5
    assert all(isinstance(r, DepResult) for r in results)
    assert [r.name for r in results] == [
        "FFmpeg", "FFprobe", "Node.js", "yt-dlp", "yt-dlp Python package"
    ]
    assert all(r.found is False for r in results)


# ------------------------------------------------------------------ #
#  Version consistency checks
# ------------------------------------------------------------------ #


def test_version_consistency_matching_versions():
    """No mismatch entry when both versions match."""
    results = [
        DepResult("yt-dlp", True, "/bin/yt-dlp.exe", "2026.08.19", required=True),
        DepResult("yt-dlp Python package", True, "/lib/yt_dlp", "2026.08.19", required=True),
    ]
    assert DependencyChecker._check_version_consistency(results) is None


def test_version_consistency_mismatched_versions():
    """Mismatch entry when versions differ."""
    results = [
        DepResult("yt-dlp", True, "/bin/yt-dlp.exe", "2026.08.19", required=True),
        DepResult("yt-dlp Python package", True, "/lib/yt_dlp", "2026.07.01", required=True),
    ]
    mismatch = DependencyChecker._check_version_consistency(results)
    assert mismatch is not None
    assert mismatch.name == "yt-dlp version sync"
    assert mismatch.found is True
    assert mismatch.required is False
    assert "2026.08.19" in mismatch.version
    assert "2026.07.01" in mismatch.version


def test_version_consistency_exe_missing():
    """No mismatch when the EXE is not found."""
    results = [
        DepResult("yt-dlp", False, None, None, required=True),
        DepResult("yt-dlp Python package", True, "/lib/yt_dlp", "2026.08.19", required=True),
    ]
    assert DependencyChecker._check_version_consistency(results) is None


def test_version_consistency_python_missing():
    """No mismatch when the Python package is not found."""
    results = [
        DepResult("yt-dlp", True, "/bin/yt-dlp.exe", "2026.08.19", required=True),
        DepResult("yt-dlp Python package", False, None, None, required=True),
    ]
    assert DependencyChecker._check_version_consistency(results) is None


def test_check_all_includes_mismatch_when_versions_differ(checker, monkeypatch):
    """check_all appends a 6th entry when the two yt-dlp versions disagree."""
    exe = checker.BIN_DIR / "yt-dlp.exe"
    exe.write_text("fake", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="2026.09.01\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    # The Python package reports its real installed version — as long as it
    # doesn't happen to be "2026.09.01" the mismatch will trigger.  We
    # explicitly mock it to a known different value.
    import types
    fake_mod = types.ModuleType("yt_dlp")
    fake_mod.__file__ = "/fake/yt_dlp/__init__.py"
    fake_version = types.ModuleType("yt_dlp.version")
    fake_version.__version__ = "2026.07.15"
    fake_mod.version = fake_version
    monkeypatch.setitem(__import__("sys").modules, "yt_dlp", fake_mod)
    monkeypatch.setitem(__import__("sys").modules, "yt_dlp.version", fake_version)

    results = checker.check_all()
    names = [r.name for r in results]
    assert "yt-dlp version sync" in names
    sync = [r for r in results if r.name == "yt-dlp version sync"][0]
    assert sync.required is False
    assert "2026.09.01" in sync.version
    assert "2026.07.15" in sync.version