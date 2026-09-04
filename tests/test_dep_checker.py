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


def test_ytdlp_installed_reports_required(checker, monkeypatch):
    import yt_dlp

    result = checker._check_ytdlp()
    assert result.found is True
    assert result.required is True
    assert result.version == yt_dlp.version.__version__


def test_ytdlp_missing_reports_required(checker, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "yt_dlp":
            raise ImportError("no yt_dlp")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = checker._check_ytdlp()
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


def test_check_all_returns_four_results(checker, no_which, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "yt_dlp":
            raise ImportError("no yt_dlp")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    results = checker.check_all()
    assert len(results) == 4
    assert all(isinstance(r, DepResult) for r in results)
    assert [r.name for r in results] == ["FFmpeg", "FFprobe", "Node.js", "yt-dlp"]
    assert all(r.found is False for r in results)