import pytest

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