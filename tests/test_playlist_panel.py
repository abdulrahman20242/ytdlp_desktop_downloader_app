import pytest

from ui.playlist_panel import (
    _fmt_duration,
    _ellipsize,
    status_style,
)


# --------------------------------------------------------------------- #
#  Duration formatting
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, ""),
        (-5, ""),
        (125, "2:05"),
        (65, "1:05"),
        (4799, "1:19:59"),
        (3600, "1:00:00"),
    ],
)
def test_fmt_duration(seconds, expected):
    assert _fmt_duration(seconds) == expected


# --------------------------------------------------------------------- #
#  Ellipsis truncation
# --------------------------------------------------------------------- #


def test_ellipsize_short_text_is_unchanged():
    assert _ellipsize("وسوم قصيرة", 200, measure=lambda s: len(s) * 2) == "وسوم قصيرة"


def test_ellipsize_truncates_long_text_to_fit():
    def measure(s):
        return len(s) * 8

    out = _ellipsize("A" * 100, 80, measure)
    assert out.endswith("…")
    assert measure(out) <= 80


def test_ellipsize_empty_and_zero_width():
    assert _ellipsize("", 100) == ""
    assert _ellipsize("نص", 0) == "نص"


def test_ellipsize_fallback_measure_without_tk():
    out = _ellipsize("X" * 50, 100)
    assert out.endswith("…")
    assert out == "X" * 11 + "…"


# --------------------------------------------------------------------- #
#  Status presentation (translation + soft colour palette)
# --------------------------------------------------------------------- #


def test_status_style_has_label_and_palette_for_every_status():
    for status in ("waiting", "downloading", "completed", "failed"):
        style = status_style(status)
        assert style["label"]
        assert style["badge_fg"]
        assert style["text_fg"]


def test_status_style_arabic_labels():
    assert status_style("waiting")["label"] == "⏳ انتظار"
    assert status_style("downloading")["label"] == "⬇ جارٍ التنزيل…"
    assert status_style("completed")["label"] == "✓ تم"
    assert status_style("failed")["label"] == "✗ فشل"


def test_status_style_completed_is_calm_and_distinct():
    completed = status_style("completed")
    downloading = status_style("downloading")
    assert completed["label"] != downloading["label"]
    assert completed["badge_fg"] != downloading["badge_fg"]
    assert completed["badge_fg"] != status_style("failed")["badge_fg"]


def test_status_style_unknown_status_falls_back_to_waiting():
    assert status_style("bogus") == status_style("waiting")