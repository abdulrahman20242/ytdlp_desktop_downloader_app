import os

import pytest

from core.format_builder import (
    QUALITY_OPTIONS,
    MODE_OPTIONS,
    FORMAT_MAP,
    FORMAT_MAP_MP4,
    build_format_opts,
    get_common_opts,
)


def test_quality_options_are_prescribed_order():
    assert QUALITY_OPTIONS[0] == "Best"
    assert QUALITY_OPTIONS == ["Best", "2160p", "1440p", "1080p", "720p", "480p", "360p"]


def test_format_maps_expose_best_alias():
    # Fixed: FORMAT_MAP/FORMAT_MAP_MP4 previously only had lowercase keys, so
    # direct indexing with the UI's "Best" label raised KeyError.
    assert FORMAT_MAP["Best"] == FORMAT_MAP["best"]
    assert FORMAT_MAP_MP4["Best"] == FORMAT_MAP_MP4["best"]


def test_mode_options_cover_all_supported():
    assert MODE_OPTIONS == ["video", "mp4_only", "audio"]


@pytest.mark.parametrize("quality", ["Best", "2160p", "1440p", "1080p", "720p", "480p", "360p"])
def test_video_mode_not_audio_uses_merged_formats_and_mp4_output(quality):
    opts = build_format_opts(quality, "video")
    assert opts["format"] == FORMAT_MAP[quality.lower()]
    assert opts["merge_output_format"] == "mp4"


@pytest.mark.parametrize("quality", ["UNKNOWN", "", "ultra"])
def test_video_mode_unknown_quality_falls_back_to_best(quality):
    opts = build_format_opts(quality, "video")
    assert opts["format"] == FORMAT_MAP["best"]
    assert opts["merge_output_format"] == "mp4"


@pytest.mark.parametrize("quality", ["2160p", "1080p", "720p"])
def test_mp4_only_mode_uses_mp4_map(quality):
    opts = build_format_opts(quality, "mp4_only")
    assert opts["format"] == FORMAT_MAP_MP4[quality]
    assert "merge_output_format" not in opts


def test_audio_mode_forces_mp3_for_unknown_audio_format():
    opts = build_format_opts("stream", "audio")
    assert opts["format"] == FORMAT_MAP["mp3"]
    assert opts["writethumbnail"] is True


def test_audio_mode_mp4_uses_m4a_format():
    opts = build_format_opts("m4a", "audio")
    assert opts["format"] == FORMAT_MAP["m4a"]


@pytest.mark.parametrize(
    ("fmt", "expected_first"),
    [
        ("mp3", "FFmpegExtractAudio"),
        ("m4a", "FFmpegMetadata"),
    ],
)
def test_audio_mode_adds_expected_postprocessors(fmt, expected_first):
    opts = build_format_opts(fmt, "audio")
    pps = opts["postprocessors"]
    assert pps[0]["key"] == expected_first
    keys = [p["key"] for p in pps]
    assert keys[0:1] == [expected_first]
    assert keys[-2:] == ["FFmpegMetadata", "EmbedThumbnail"]


def test_mp3_audio_postprocessor_configures_quality():
    pps = build_format_opts("mp3", "audio")["postprocessors"]
    extract = next(p for p in pps if p["key"] == "FFmpegExtractAudio")
    assert extract["preferredcodec"] == "mp3"
    assert extract["preferredquality"] == "192"


def test_audio_postprocessors_embed_thumbnail_and_metadata():
    pps = build_format_opts("m4a", "audio")["postprocessors"]
    keys = [p["key"] for p in pps]
    assert "EmbedThumbnail" in keys
    assert any(p.get("add_metadata") for p in pps if p["key"] == "FFmpegMetadata")


class _FakeConfig:
    def __init__(self, data):
        self._data = data

    def get(self, key, default=None):
        keys = key.split(".")
        obj = self._data
        for k in keys:
            if isinstance(obj, dict):
                obj = obj.get(k)
                if obj is None:
                    return default
            else:
                return default
        return obj


@pytest.fixture
def fake_config():
    return _FakeConfig(
        {
            "download": {"concurrent_fragments": 6, "retries": 3},
            "advanced": {"extractor_args": {"custom": {"flag": 1}}},
        }
    )


@pytest.fixture
def bin_dir(tmp_path):
    p = tmp_path / "bin"
    p.mkdir()
    return p


def test_get_common_opts_sets_bin_dir_into_path(fake_config, bin_dir, monkeypatch):
    monkeypatch.setenv("PATH", "C:\\original")
    opts = get_common_opts(str(bin_dir), fake_config)
    assert opts["ffmpeg_location"] == str(bin_dir.resolve())
    assert os.environ["PATH"].startswith(str(bin_dir.resolve()))
    assert "C:\\original" in os.environ["PATH"]


def test_get_common_opts_reads_concurrency_and_retries_from_config(fake_config, bin_dir):
    opts = get_common_opts(str(bin_dir), fake_config)
    assert opts["concurrent_fragments"] == 6
    assert opts["retries"] == 3
    assert opts["fragment_retries"] == 3


def test_get_common_opts_merges_user_extractor_args(fake_config, bin_dir):
    opts = get_common_opts(str(bin_dir), fake_config)
    assert opts["extractor_args"]["youtube-ejs"] == {}
    assert opts["extractor_args"]["custom"] == {"flag": 1}


def test_get_common_opts_merges_extra_keys_into_existing_extractor_args(bin_dir):
    config = _FakeConfig(
        {
            "advanced": {
                "extractor_args": {
                    "youtube-ejs": {"extra": "value"},
                }
            }
        }
    )
    opts = get_common_opts(str(bin_dir), config)
    assert opts["extractor_args"]["youtube-ejs"] == {"extra": "value"}


def test_get_common_opts_defaults_when_config_missing(bin_dir):
    opts = get_common_opts(str(bin_dir), _FakeConfig({}))
    assert opts["concurrent_fragments"] == 4
    assert opts["retries"] == 10
    assert opts["extractor_args"]["youtube-ejs"] == {}


def test_get_common_opts_keep_silent_and_quiet_flags(bin_dir):
    opts = get_common_opts(str(bin_dir), _FakeConfig({}))
    assert opts["quiet"] is False
    assert opts["no_warnings"] is True
    assert opts["ignoreerrors"] is False
    assert opts["throttledratelimit"] == 102400


def test_get_common_opts_forces_single_video_mode(bin_dir):
    # A watch URL carrying list= params must never pull the whole playlist.
    opts = get_common_opts(str(bin_dir), _FakeConfig({}))
    assert opts["noplaylist"] is True


def test_build_format_opts_wires_merge_output_from_config():
    cfg = _FakeConfig({"download": {"merge_output_format": "mkv"}})
    opts = build_format_opts("720p", "video", cfg)
    assert opts["format"] == FORMAT_MAP["720p"]
    assert opts["merge_output_format"] == "mkv"


def test_build_format_opts_defaults_merge_output_to_mp4_when_no_config():
    assert build_format_opts("720p", "video")["merge_output_format"] == "mp4"
    assert build_format_opts("720p", "video", _FakeConfig({}))["merge_output_format"] == "mp4"


def test_build_format_opts_mp3_bitrate_is_fixed_and_not_read_from_config():
    cfg = _FakeConfig({"audio": {"mp3_quality": "320"}})
    pps = build_format_opts("mp3", "audio", cfg)["postprocessors"]
    extract = next(p for p in pps if p["key"] == "FFmpegExtractAudio")
    assert extract["preferredquality"] == "192"


def test_get_common_opts_wires_verbose_from_show_debug_logs(bin_dir):
    on = get_common_opts(str(bin_dir), _FakeConfig({"advanced": {"show_debug_logs": True}}))
    off = get_common_opts(str(bin_dir), _FakeConfig({"advanced": {"show_debug_logs": False}}))
    missing = get_common_opts(str(bin_dir), _FakeConfig({}))
    assert on["verbose"] is True
    assert off["verbose"] is False
    assert missing["verbose"] is False