import tkinter as tk

import pytest

import ui.playlist_panel as pp

from ui.playlist_panel import (
    PlaylistPanel,
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


@pytest.mark.parametrize(
    ("status", "expected_label", "expected_badge_fg", "expected_text_fg"),
    [
        ("waiting", "⏳ انتظار", "#2a2a2a", "#9a9a9a"),
        ("downloading", "⬇ جارٍ التنزيل…", "#1f3a52", "#6fc3ff"),
        ("completed", "✓ تم", "#1d3325", "#7fd18a"),
        ("failed", "✗ فشل", "#3a2522", "#ff958c"),
    ],
)
def test_status_style_defines_label_and_palette(
    status, expected_label, expected_badge_fg, expected_text_fg
):
    style = status_style(status)
    assert style["label"] == expected_label
    assert style["badge_fg"] == expected_badge_fg
    assert style["text_fg"] == expected_text_fg


def test_status_style_completed_is_calm_and_distinct():
    completed = status_style("completed")
    downloading = status_style("downloading")
    assert completed["label"] != downloading["label"]
    assert completed["badge_fg"] != downloading["badge_fg"]
    assert completed["badge_fg"] != status_style("failed")["badge_fg"]


def test_status_style_unknown_status_falls_back_to_waiting():
    assert status_style("bogus") == status_style("waiting")


# --------------------------------------------------------------------- #
#  PlaylistPanel interaction & state
# --------------------------------------------------------------------- #


def test_selected_entries_filters_by_checkbox_state(tk_root):
    panel = PlaylistPanel(tk_root)
    sample_playlist = {
        "title": "Test Playlist",
        "entries": [
            {"index": 1, "title": "Song 1", "url": "https://youtu.be/1"},
            {"index": 2, "title": "Song 2", "url": "https://youtu.be/2"},
            {"index": 3, "title": "Song 3", "url": "https://youtu.be/3"},
        ],
    }
    panel.set_playlist(sample_playlist)
    assert panel.selected_entries() == []

    panel._rows[0]["var"].set(True)
    panel._rows[2]["var"].set(True)
    selected = panel.selected_entries()
    assert len(selected) == 2
    assert selected[0]["title"] == "Song 1"
    assert selected[1]["title"] == "Song 3"


def test_begin_download_marks_queued_rows_waiting_and_disables_controls(tk_root):
    panel = PlaylistPanel(tk_root)
    sample_playlist = {
        "title": "Test Playlist",
        "entries": [
            {"index": 1, "title": "Song 1"},
            {"index": 2, "title": "Song 2"},
        ],
    }
    panel.set_playlist(sample_playlist)
    panel.begin_download(subset_indices=[2])

    assert panel._rows[0]["status_var"].get() == ""
    assert panel._rows[1]["status_var"].get() == "⏳ انتظار"
    assert panel._select_all_btn.cget("state") == "disabled"
    assert panel._deselect_all_btn.cget("state") == "disabled"


def test_finish_download_re_enables_controls(tk_root):
    panel = PlaylistPanel(tk_root)
    sample_playlist = {
        "title": "Test Playlist",
        "entries": [{"index": 1, "title": "Song 1"}],
    }
    panel.set_playlist(sample_playlist)
    panel.begin_download()
    assert panel._select_all_btn.cget("state") == "disabled"

    panel.finish_download()
    assert panel._select_all_btn.cget("state") == "normal"
    assert panel._deselect_all_btn.cget("state") == "normal"


def test_update_item_updates_matching_row_status(tk_root):
    panel = PlaylistPanel(tk_root)
    sample_playlist = {
        "title": "Test Playlist",
        "entries": [
            {"index": 1, "title": "Song 1"},
            {"index": 2, "title": "Song 2"},
        ],
    }
    panel.set_playlist(sample_playlist)
    panel.update_item(2, "completed")

    assert panel._rows[0]["status_var"].get() == ""
    assert panel._rows[1]["status_var"].get() == "✓ تم"


def test_select_all_and_deselect_all_toggle_all_rows(tk_root):
    panel = PlaylistPanel(tk_root)
    sample_playlist = {
        "title": "Test Playlist",
        "entries": [
            {"index": 1, "title": "Song 1"},
            {"index": 2, "title": "Song 2"},
        ],
    }
    panel.set_playlist(sample_playlist)

    panel._select_all()
    assert all(row["var"].get() is True for row in panel._rows)

    panel._deselect_all()
    assert all(row["var"].get() is False for row in panel._rows)


# --------------------------------------------------------------------- #
#  Scaling, layout and lifecycle
# --------------------------------------------------------------------- #


def test_scale_rounds_for_display_scaling(monkeypatch, tk_root):
    monkeypatch.setattr(pp.ScalingTracker, "get_widget_scaling", lambda widget: 2.0)
    panel = PlaylistPanel(tk_root)
    assert panel._scale(50) == 25
    assert panel._scale(1) == 1


def test_scale_falls_back_to_raw_pixels_on_error(monkeypatch, tk_root):
    panel = PlaylistPanel(tk_root)

    def boom(widget):
        raise tk.TclError("no display")

    monkeypatch.setattr(pp.ScalingTracker, "get_widget_scaling", boom)
    assert panel._scale(120) == 120


def test_set_playlist_repopulation_destroys_previous_rows(tk_root):
    panel = PlaylistPanel(tk_root)
    panel.set_playlist({
        "title": "P", "entries": [{"index": 1, "title": "A"}],
    })
    first_frames = [row["frame"] for row in panel._rows]

    panel.set_playlist({
        "title": "P2",
        "entries": [{"index": 1, "title": "B"}, {"index": 2, "title": "C"}],
    })

    assert len(panel._rows) == 2
    assert all(not frame.winfo_exists() for frame in first_frames)


def test_set_playlist_reschedules_scroll_sync_when_mapped(monkeypatch, tk_root):
    panel = PlaylistPanel(tk_root)
    scheduled = []
    monkeypatch.setattr(panel, "winfo_ismapped", lambda: True)
    monkeypatch.setattr(panel, "after", lambda ms, fn, *args: scheduled.append((ms, fn)))
    panel.set_playlist({"title": "P", "entries": []})
    assert scheduled and scheduled[-1][0] == 0


def test_show_schedules_scroll_sync(monkeypatch, tk_root):
    panel = PlaylistPanel(tk_root)
    scheduled = []
    monkeypatch.setattr(panel, "after", lambda ms, fn, *args: scheduled.append((ms, fn)))
    panel.show()
    assert scheduled and scheduled[-1][0] == 1


def test_hide_removes_widget_from_grid(tk_root):
    panel = PlaylistPanel(tk_root)
    panel.show()
    panel.hide()
    assert panel.winfo_manager() == ""


# --------------------------------------------------------------------- #
#  Header / row population
# --------------------------------------------------------------------- #


def test_refresh_header_with_uploader_shows_channel(tk_root):
    panel = PlaylistPanel(tk_root)
    panel._refresh_header({
        "title": "Mix", "uploader": "Creator", "entries": [{"index": 1}],
    })
    assert panel._meta_channel.cget("text") == "Creator"
    assert panel._meta_count.cget("text") == "1 فيديو"


def test_refresh_header_without_uploader_hides_channel(tk_root):
    panel = PlaylistPanel(tk_root)
    panel._refresh_header({"title": "Mix", "entries": [{"index": 1}]})
    assert panel._meta_channel.grid_info() == {}


def test_refresh_header_with_thumbnail_loads_panel_thumb(monkeypatch, tk_root):
    panel = PlaylistPanel(tk_root)
    loaded = []
    monkeypatch.setattr(
        panel, "_load_thumb", lambda label, url, size: loaded.append((label, url))
    )
    panel._refresh_header({"title": "Mix", "thumbnail": "http://img/h.jpg"})
    assert loaded and loaded[0][0] is panel._panel_thumb


def test_add_row_with_duration_and_thumbnail(monkeypatch, tk_root):
    panel = PlaylistPanel(tk_root)
    panel.set_playlist({"title": "P", "entries": []})
    loaded = []
    monkeypatch.setattr(
        panel, "_load_thumb", lambda label, url, size: loaded.append((label, url))
    )
    panel._add_row({
        "index": 5, "title": "Song", "duration": 125, "thumbnail": "http://img/t.jpg",
    })

    row = panel._rows[-1]
    assert row["meta_lbl"].grid_info() != {}
    assert loaded and loaded[0][0] is row["thumb_lbl"]


# --------------------------------------------------------------------- #
#  Thumbnail loading
# --------------------------------------------------------------------- #


class _StubImage:
    def resize(self, size, resample):
        return self


class _StubPhoto:
    pass


class _StubResp:
    def __init__(self, content=b"imgbytes"):
        self.content = content

    def raise_for_status(self):
        return None


class _SyncThread:
    def __init__(self, target, daemon=False):
        self._target = target
        self.daemon = daemon

    def start(self):
        self._target()


class _ThumbLabelStub:
    def __init__(self):
        self.calls = []

    def configure(self, **kwargs):
        self.calls.append(kwargs)


def test_load_thumb_applies_image_on_main_thread(monkeypatch, tk_root):
    photo = _StubPhoto()

    monkeypatch.setattr(pp.requests, "get", lambda url, timeout=10: _StubResp())
    monkeypatch.setattr(pp.Image, "open", lambda buf: _StubImage())
    monkeypatch.setattr(pp.ctk, "CTkImage", lambda img, size: photo)
    monkeypatch.setattr(pp.threading, "Thread", _SyncThread)

    panel = PlaylistPanel(tk_root)
    scheduled = []
    monkeypatch.setattr(panel, "after", lambda ms, fn, *args: scheduled.append((ms, fn)))

    label = _ThumbLabelStub()
    panel._load_thumb(label, "http://img/t.jpg", (80, 45))

    assert scheduled
    apply_fn = scheduled[0][1]
    apply_fn()
    assert label.calls == [{"image": photo, "text": ""}]


def test_load_thumb_logs_request_failure(monkeypatch, tk_root, caplog):
    def failing_get(url, timeout=10):
        raise pp.requests.RequestException("boom")

    monkeypatch.setattr(pp.requests, "get", failing_get)
    monkeypatch.setattr(pp.threading, "Thread", _SyncThread)

    panel = PlaylistPanel(tk_root)
    with caplog.at_level("DEBUG", logger="ui.playlist_panel"):
        panel._load_thumb(_ThumbLabelStub(), "http://img/t.jpg", (80, 45))

    assert "Could not load playlist thumbnail" in caplog.text


def test_load_thumb_tolerates_destroyed_label(monkeypatch, tk_root):
    photo = _StubPhoto()

    monkeypatch.setattr(pp.requests, "get", lambda url, timeout=10: _StubResp())
    monkeypatch.setattr(pp.Image, "open", lambda buf: _StubImage())
    monkeypatch.setattr(pp.ctk, "CTkImage", lambda img, size: photo)
    monkeypatch.setattr(pp.threading, "Thread", _SyncThread)

    panel = PlaylistPanel(tk_root)
    scheduled = []
    monkeypatch.setattr(panel, "after", lambda ms, fn, *args: scheduled.append((ms, fn)))

    class _BoomLabel:
        def configure(self, **kwargs):
            raise tk.TclError("widget destroyed")

    panel._load_thumb(_BoomLabel(), "http://img/t.jpg", (80, 45))
    scheduled[0][1]()


# --------------------------------------------------------------------- #
#  Hover / selection interaction
# --------------------------------------------------------------------- #


def test_row_hover_updates_background_and_flag(tk_root):
    panel = PlaylistPanel(tk_root)
    panel.set_playlist({"title": "P", "entries": [{"index": 1, "title": "A"}]})
    row = panel._rows[0]

    panel._on_row_enter(row)
    assert row["hovered"] is True
    assert row["frame"].cget("fg_color") == panel._ROW_HOVER_BG

    panel._on_row_leave(row)
    assert row["hovered"] is False
    assert row["frame"].cget("fg_color") == "transparent"


def test_row_toggle_updates_background_and_selection_label(tk_root):
    panel = PlaylistPanel(tk_root)
    panel.set_playlist({
        "title": "P",
        "entries": [{"index": 1, "title": "A"}, {"index": 2, "title": "B"}],
    })
    row = panel._rows[0]
    row["var"].set(True)

    panel._on_row_toggle(row)

    assert row["frame"].cget("fg_color") == panel._ROW_SELECT_BG
    assert panel._sel_label.cget("text") == "1 محددة"


# --------------------------------------------------------------------- #
#  Font measurement and truncation
# --------------------------------------------------------------------- #


def test_measure_font_creates_and_caches(tk_root):
    panel = PlaylistPanel(tk_root)
    first = panel._measure_font()
    second = panel._measure_font()
    assert first is second
    assert first is not False


def test_measure_fonts_handle_tk_unavailable(monkeypatch, tk_root):
    def boom(*args, **kwargs):
        raise RuntimeError("no display")

    monkeypatch.setattr(pp.tkfont, "Font", boom)
    panel = PlaylistPanel(tk_root)
    assert panel._measure_font() is None
    assert panel._measure_bold_font() is None


def test_schedule_truncation_tolerates_cancel_failure(monkeypatch, tk_root):
    panel = PlaylistPanel(tk_root)
    panel._truncate_after = 123
    scheduled = []
    monkeypatch.setattr(panel, "after", lambda ms, fn, *args: scheduled.append((ms, fn)))
    monkeypatch.setattr(panel, "after_cancel", lambda ident: (_ for _ in ()).throw(ValueError("gone")))

    panel._schedule_truncation()
    assert scheduled == [(50, panel._refresh_row_truncation)]

    monkeypatch.setattr(panel, "after_cancel", lambda ident: None)
    panel._schedule_truncation()
    assert len(scheduled) == 2


def test_refresh_row_truncation_ignores_destroyed_widget(monkeypatch, tk_root):
    panel = PlaylistPanel(tk_root)
    panel.set_playlist({"title": "P", "entries": [{"index": 1, "title": "A"}]})

    def boom():
        raise tk.TclError("widget destroyed")

    monkeypatch.setattr(panel._list, "winfo_width", boom)
    panel._refresh_row_truncation()


def test_refresh_row_truncation_returns_for_tiny_width(monkeypatch, tk_root):
    panel = PlaylistPanel(tk_root)
    panel.set_playlist({"title": "P", "entries": [{"index": 1, "title": "A"}]})
    monkeypatch.setattr(panel._list, "winfo_width", lambda: 10)
    panel._refresh_row_truncation()


def test_refresh_row_truncation_uses_full_title_without_font(monkeypatch, tk_root):
    def boom(*args, **kwargs):
        raise RuntimeError("no display")

    monkeypatch.setattr(pp.tkfont, "Font", boom)

    panel = PlaylistPanel(tk_root)
    panel.set_playlist({"title": "P", "entries": [{"index": 1, "title": "Plain Title"}]})
    long_title = "A very long title " * 6
    panel.set_playlist({"title": "P2", "entries": [{"index": 1, "title": long_title}]})

    monkeypatch.setattr(panel._list, "winfo_width", lambda: 700)
    panel._refresh_row_truncation()

    assert panel._rows[0]["title_lbl"].cget("text") == long_title


def test_refresh_row_truncation_applies_ellipsis(monkeypatch, tk_root):
    panel = PlaylistPanel(tk_root)
    long_title = "A very long title " * 6
    panel.set_playlist({
        "title": "A Very Long Playlist Title " * 10,
        "entries": [{"index": 1, "title": long_title}],
    })
    monkeypatch.setattr(panel._list, "winfo_width", lambda: 700)

    panel._refresh_row_truncation()

    assert "…" in panel._rows[0]["title_lbl"].cget("text")
    assert "…" in panel._meta_title.cget("text")
    assert panel._rows[0]["title_lbl"].cget("wraplength") == 700 - panel._FIXED_ROW_WIDTH