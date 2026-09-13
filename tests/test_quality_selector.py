import pytest

from core.format_builder import QUALITY_OPTIONS
from ui.quality_selector import AUDIO_FORMATS, QualitySelector


def test_quality_selector_defaults_to_video_and_1080p(tk_root):
    qs = QualitySelector(tk_root)
    assert qs.mode == "video"
    assert qs.quality == "1080p"


def test_mode_change_to_audio_switches_to_audio_formats(tk_root):
    qs = QualitySelector(tk_root)
    qs._on_mode_change("audio")

    assert qs.mode == "video"  # variable updated by OptionMenu command in real UI
    qs._mode_var.set("audio")
    assert qs.mode == "audio"
    assert qs.quality == "mp3"
    assert qs._quality_menu.cget("values") == AUDIO_FORMATS


def test_mode_change_from_audio_to_video_restores_video_qualities(tk_root):
    qs = QualitySelector(tk_root)
    qs.apply_defaults("audio", "MP3")
    assert qs.quality == "mp3"

    qs._on_mode_change("video")
    assert qs.quality == "1080p"
    assert qs._quality_menu.cget("values") == QUALITY_OPTIONS


@pytest.mark.parametrize(
    ("input_mode", "input_quality", "expected_mode", "expected_quality"),
    [
        ("audio", "1080p", "audio", "mp3"),
        ("video", "720p", "video", "720p"),
        ("mp4_only", "480p", "mp4_only", "480p"),
    ],
)
def test_apply_defaults_configures_mode_and_quality(
    tk_root, input_mode, input_quality, expected_mode, expected_quality
):
    qs = QualitySelector(tk_root)
    qs.apply_defaults(input_mode, input_quality)
    assert qs.mode == expected_mode
    assert qs.quality == expected_quality


@pytest.mark.parametrize(
    ("input_mode", "input_quality", "expected_mode", "expected_quality"),
    [
        ("bogus_mode", "720p", "video", "720p"),
        ("video", "4K Ultra", "video", "1080p"),
        ("bogus_mode", "4K Ultra", "video", "1080p"),
    ],
)
def test_apply_defaults_falls_back_on_unknown_mode_or_quality(
    tk_root, input_mode, input_quality, expected_mode, expected_quality
):
    qs = QualitySelector(tk_root)
    qs.apply_defaults(input_mode, input_quality)
    assert qs.mode == expected_mode
    assert qs.quality == expected_quality


def test_set_qualities_adjusts_selection_when_current_not_in_list(tk_root):
    qs = QualitySelector(tk_root)
    qs._quality_var.set("1080p")

    qs.set_qualities(["720p", "480p"])
    assert qs.quality == "720p"
    assert qs._quality_menu.cget("values") == ["720p", "480p"]


def test_set_qualities_preserves_current_if_present(tk_root):
    qs = QualitySelector(tk_root)
    qs._quality_var.set("720p")

    qs.set_qualities(["1080p", "720p", "480p"])
    assert qs.quality == "720p"


def test_set_qualities_ignored_in_audio_mode(tk_root):
    qs = QualitySelector(tk_root)
    qs.apply_defaults("audio", "MP3")

    qs.set_qualities(["1080p", "720p"])
    assert qs.quality == "mp3"
    assert qs._quality_menu.cget("values") == AUDIO_FORMATS
