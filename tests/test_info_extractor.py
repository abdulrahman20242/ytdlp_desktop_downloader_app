import pytest

from core import info_extractor
from core.info_extractor import (
    get_available_qualities,
    extract_info,
    extract_thumbnail,
    extract_title,
    extract_duration,
    extract_uploader,
)


class _FakeYDL:
    def __init__(self, info=None, fail=None):
        self._info = info
        self._fail = fail
        self._sanitize_called = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=False):
        if self._fail:
            raise self._fail
        self._sanitize_called = True
        return self._info

    def sanitize_info(self, info):
        return info


def test_extract_info_returns_sanitized_info_on_success(monkeypatch):
    fake = _FakeYDL(info={"id": "abc", "title": "T"})
    monkeypatch.setattr(info_extractor, "YoutubeDL", lambda opts: fake)
    result = extract_info("https://youtu.be/x")
    assert result == {"id": "abc", "title": "T"}
    assert fake._sanitize_called is True


def test_extract_info_returns_none_on_extractor_failure(monkeypatch):
    fake = _FakeYDL(fail=RuntimeError("network down"))
    monkeypatch.setattr(info_extractor, "YoutubeDL", lambda opts: fake)
    assert extract_info("https://youtu.be/x") is None


@pytest.mark.parametrize(
    ("heights", "expected"),
    [
        # Semantics: get_available_qualities returns "Best" + every preset tier
        # whose threshold <= the maximum height present in the video.
        ([2160], ["Best", "2160p", "1440p", "1080p", "720p", "480p", "360p", "240p"]),
        ([1080, 720, 480], ["Best", "1080p", "720p", "480p", "360p", "240p"]),
        ([360, 240], ["Best", "360p", "240p"]),
        ([], ["Best"]),
        ([1440], ["Best", "1440p", "1080p", "720p", "480p", "360p", "240p"]),
    ],
)
def test_get_available_qualities_derives_from_heights(heights, expected, monkeypatch):
    def fake_extract(url):
        return {"formats": [{"height": h} for h in heights]}

    monkeypatch.setattr(info_extractor, "extract_info", fake_extract)
    assert get_available_qualities("https://x") == expected


def test_get_available_qualities_falls_back_to_best_on_error(monkeypatch):
    def boom(url):
        return None

    monkeypatch.setattr(info_extractor, "extract_info", boom)
    assert get_available_qualities("https://x") == ["Best"]


@pytest.mark.parametrize(
    ("info", "expected"),
    [
        ({"thumbnail": "http://img/x.jpg"}, "http://img/x.jpg"),
        ({}, None),
    ],
)
def test_extract_thumbnail(info, expected):
    assert extract_thumbnail(info) == expected


@pytest.mark.parametrize(
    ("info", "expected"),
    [
        ({"title": "My Video"}, "My Video"),
        ({}, ""),
    ],
)
def test_extract_title(info, expected):
    assert extract_title(info) == expected


@pytest.mark.parametrize(
    ("info", "expected"),
    [
        ({"duration": 125}, 125),
        ({}, 0),
    ],
)
def test_extract_duration(info, expected):
    assert extract_duration(info) == expected


@pytest.mark.parametrize(
    ("info", "expected"),
    [
        ({"uploader": "Channel Name"}, "Channel Name"),
        ({}, ""),
    ],
)
def test_extract_uploader(info, expected):
    assert extract_uploader(info) == expected