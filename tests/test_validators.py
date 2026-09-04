import pytest

from utils.validators import (
    PLAYLIST_RE,
    is_valid_youtube_url,
    is_playlist_url,
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
        "https://vimeo.com/123456",
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
    ],
)
def test_short_video_id_still_accepted_because_group_is_optional(url):
    # The [\w-]{11} group is unanchored and optional, so any trailing value
    # after a recognized path prefix passes validation.
    assert is_valid_youtube_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://youtu.be/dQw4w9WgXcQ",
        "http://youtu.be/dQw4w9WgXcQ",
        "youtu.be/dQw4w9WgXcQ",
    ],
)
def test_bare_youtu_be_short_links_are_rejected_by_current_regex(url):
    # Production gap: YOUTUBE_RE's branch group never leaves room for the
    # youtu.be/<id> shorthand, so share links of that form are not recognized.
    # Kept as a live regression test for this behavior.
    assert is_valid_youtube_url(url) is False


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLx9x&index=1", True),
        ("https://www.youtube.com/playlist?list=PLx9x", True),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ&list=PLx9x", True),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&index=1", False),
        ("https://example.com/playlist?list=PLx9x", False),
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
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "dQw4w9WgXcQ"),
        ("https://example.com/no-video-id", None),
        ("", None),
    ],
)
def test_extracts_video_id_by_url_shape(url, video_id):
    assert extract_video_id(url) == video_id


def test_playlist_regex_matches_stripped_url_with_leading_whitespace():
    assert PLAYLIST_RE.search(
        "   https://www.youtube.com/watch?v=x&list=PL_ACB&t=1".strip()
    )