import pytest
from pathlib import Path

from utils.file_utils import (
    safe_filename,
    sanitize_folder_name,
    get_downloads_dir,
    ensure_dir,
)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Rick Astley - Never Gonna Give You Up.mp4", "Rick Astley - Never Gonna Give You Up.mp4"),
        ('a:b\\c/d*e?f"g<h>i|j', "a_b_c_d_e_f_g_h_i_j"),
        ("  padded name  ", "padded name"),
        ("", ""),
        ("tab\ttab", "tab\ttab"),
    ],
)
def test_safe_filename_replaces_windows_invalid_chars(name, expected):
    assert safe_filename(name) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("My Mix #1", "My Mix #1"),
        ('a:b\\c/d*e?f"g<h>i|j', "a_b_c_d_e_f_g_h_i_j"),
        ("  spaced  title  ", "spaced title"),
        ("Trailing dot. ", "Trailing dot"),
        ("CON", "_CON"),
        ("con.txt", "_con.txt"),
        ("LPT9 playlist", "LPT9 playlist"),
        ("LPT9", "_LPT9"),
        ("slow\tmix", "slow_mix"),
        ("", "Playlist"),
        ("   ", "Playlist"),
        ("x" * 200, "x" * 80),
    ],
)
def test_sanitize_folder_name_is_windows_safe(title, expected):
    assert sanitize_folder_name(title) == expected


def test_sanitize_folder_name_uses_custom_fallback():
    assert sanitize_folder_name("", "قائمة تشغيل") == "قائمة تشغيل"


def test_get_downloads_dir_is_under_home(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    result = get_downloads_dir()
    assert result.name == "YTDownloader"
    assert result.parent.name == "Downloads"
    assert str(result).startswith(str(tmp_path))


def test_ensure_dir_creates_nested_path(tmp_path):
    target = tmp_path / "a" / "b" / "c"
    result = ensure_dir(target)
    assert result == target
    assert target.is_dir()


def test_ensure_dir_with_spaces_and_non_ascii(tmp_path):
    target = tmp_path / "حفظ مقاطع" / "my folder"
    result = ensure_dir(target)
    assert result == target
    assert target.is_dir()


def test_ensure_dir_target_is_existing_file_uses_fallback(tmp_path):
    blocked = tmp_path / "blocked"
    blocked.write_text("I am a file, not a directory", encoding="utf-8")
    fallback = tmp_path / "fallback_dir"
    result = ensure_dir(blocked, fallback=fallback)
    assert result == fallback
    assert fallback.is_dir()


def test_ensure_dir_target_is_existing_file_without_fallback_raises(tmp_path):
    blocked = tmp_path / "blocked"
    blocked.write_text("file", encoding="utf-8")
    with pytest.raises(OSError):
        ensure_dir(blocked)


def test_ensure_dir_falls_back_when_primary_mkdir_fails(monkeypatch, tmp_path):
    primary = tmp_path / "primary"
    fallback = tmp_path / "fallback"
    orig_mkdir = Path.mkdir

    def deny_primary(self, **kwargs):
        if self == primary:
            raise PermissionError(13, "Access denied", str(self))
        return orig_mkdir(self, **kwargs)

    monkeypatch.setattr(Path, "mkdir", deny_primary)
    result = ensure_dir(primary, fallback=fallback)
    assert result == fallback
    assert fallback.is_dir()


def test_ensure_dir_propagates_when_fallback_also_fails(monkeypatch, tmp_path):
    def deny_all(self, **kwargs):
        raise PermissionError(13, "Access denied", str(self))

    monkeypatch.setattr(Path, "mkdir", deny_all)
    with pytest.raises(PermissionError):
        ensure_dir(tmp_path / "primary", fallback=tmp_path / "fallback")