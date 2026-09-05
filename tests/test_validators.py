import pytest

from utils.validators import (
    PLAYLIST_RE,
    is_valid_youtube_url,
    is_playlist_url,
    is_explicit_playlist_url,
    classify_url,
    extract_video_id,
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", True),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ", True),
        ("youtube.com/watch?v=dQw4w9WgXcQ", True),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", True),
        ("https://www.youtube.com/v/dQw4w9WgXcQ", True),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", True),
        ("  https://www.youtube.com/watch?v=dQw4w9WgXcQ  ", True),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s", True),
        ("https://www.youtube.com/watch?feature=share&v=dQw4w9WgXcQ", True),
        ("https://youtu.be/dQw4w9WgXcQ", True),
        ("https://youtu.be/dQw4w9WgXcQ?si=AbCdEfGh123", True),
    ],
)
def test_detects_valid_youtube_url(url, expected):
    assert is_valid_youtube_url(url) is expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "https://example.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com",
        "https://www.youtube.com/watch",
        "https://www.youtube.com/watch?v=",
        "https://vimeo.com/123456",
        "https://youtu.be/",
        "just some text",
    ],
)
def test_rejects_non_youtube_or_malformed_url(url):
    assert is_valid_youtube_url(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "https://youtube.com/watch?v=short",
        "youtube.com/watch?v=xy",
        "https://www.youtube.com/watch?v=1",
        "https://youtube.com/watch?v=",
        "https://youtu.be/short",
        "https://youtu.be/dQw4w9WgXcQ-extra",
    ],
)
def test_short_or_malformed_video_id_is_rejected(url):
    # The video-id branch now requires exactly 11 word chars (neg. lookahead),
    # so short, empty, or over-long ids are rejected instead of silently passing.
    assert is_valid_youtube_url(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "https://youtu.be/dQw4w9WgXcQ",
        "http://youtu.be/dQw4w9WgXcQ",
        "youtu.be/dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ?si=AbCdEfGh123",
    ],
)
def test_bare_youtu_be_short_links_are_accepted(url):
    # Fixed: the regex now recognizes the youtu.be/<id> shorthand.
    assert is_valid_youtube_url(url) is True


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLx9x&index=1", True),
        ("https://www.youtube.com/playlist?list=PLx9x", True),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ&list=PLx9x", True),
        ("https://youtu.be/dQw4w9WgXcQ?list=PLx9x", True),
        ("http://youtu.be/dQw4w9WgXcQ?list=PLx9x&t=1", True),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&index=1", False),
        ("https://example.com/playlist?list=PLx9x", False),
        ("https://youtu.be/dQw4w9WgXcQ", False),
    ],
)
def test_detects_playlist_url(url, expected):
    assert is_playlist_url(url) is expected


@pytest.mark.parametrize(
    ("url", "video_id"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/1-2-3-4-5-6", "1-2-3-4-5-6"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "dQw4w9WgXcQ"),
        ("https://example.com/no-video-id", None),
        ("", None),
    ],
)
def test_extracts_video_id_by_url_shape(url, video_id):
    assert extract_video_id(url) == video_id


@pytest.mark.parametrize(
    "url",
    [
        "https://youtu.be/dQw4w9WgXcQextra",
        "https://youtu.be/1-2-3-4-5-6-7-8-9-0-1",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQDwqw",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ-extra",
        "https://www.youtube.com/embed/dQw4w9WgXcQ_-suffix",
    ],
)
def test_does_not_truncate_overlong_video_id(url):
    # The id must be exactly 11 chars; an extra [\w-] right after must
    # invalidate the match instead of silently truncating to 11.
    assert extract_video_id(url) is None


def test_playlist_regex_matches_stripped_url_with_leading_whitespace():
    assert PLAYLIST_RE.search(
        "   https://www.youtube.com/watch?v=x&list=PL_ACB&t=1".strip()
    )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/playlist?list=PLx9x", True),
        ("https://youtube.com/playlist?list=PLx9x", True),
        ("https://www.youtube.com/playlist?tab=pe&list=PLx9x", True),
        ("http://youtube.com/playlist?list=PLx9x&index=3", True),
        # watch/shorts/youtu.be URLs with a list param are NOT explicit playlists
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLx9x", False),
        ("https://youtu.be/dQw4w9WgXcQ?list=PLx9x", False),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ?list=PLx9x", False),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", False),
        ("https://example.com/playlist?list=PLx9x", False),
        ("", False),
    ],
)
def test_detects_explicit_playlist_url(url, expected):
    assert is_explicit_playlist_url(url) is expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # Explicit playlist links always classify as playlist
        ("https://www.youtube.com/playlist?list=PLx9x", "playlist"),
        ("https://youtube.com/playlist?list=PLx9x&index=2", "playlist"),
        # Videos stay videos even when playlist params are attached
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLx9x&index=1", "video"),
        ("https://youtu.be/dQw4w9WgXcQ?list=PLx9x", "video"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ?list=PLx9x", "video"),
        # Plain video URLs
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "video"),
        ("https://youtu.be/dQw4w9WgXcQ", "video"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "video"),
        ("https://www.youtube.com/v/dQw4w9WgXcQ", "video"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "video"),
        # Invalid / other sites
        ("", None),
        ("https://example.com", None),
        ("just some text", None),
        ("https://www.youtube.com", None),
    ],
)
def test_classify_url_routes_playlist_vs_single_video(url, expected):
    assert classify_url(url) is expected