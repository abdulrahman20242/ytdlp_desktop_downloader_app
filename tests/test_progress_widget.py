import pytest

from ui.progress_widget import ProgressWidget


class _FakeBar:
    def set(self, value):
        self.value = value


class _FakeLabel:
    def configure(self, **kwargs):
        self.kwargs = kwargs


class _FakeApp:
    def __init__(self):
        self._progress_bar = _FakeBar()
        self._info_label = _FakeLabel()
        self._filename_label = _FakeLabel()
        self._progress_bar.set(0)


def _widget_no_display():
    widget = object.__new__(ProgressWidget)
    widget._progress_bar = _FakeBar()
    widget._info_label = _FakeLabel()
    widget._filename_label = _FakeLabel()
    return widget


@pytest.mark.parametrize(
    ("d", "expected"),
    [
        ({"downloaded_bytes": 5, "total_bytes": 10}, 0.5),
        ({"downloaded_bytes": 10, "total_bytes": 5}, 1.0),
        ({"downloaded_bytes": 0, "total_bytes": 0}, 0.0),
        ({"downloaded_bytes": 3, "total_bytes_estimate": 6}, 0.5),
        ({"downloaded_bytes": 3}, 0.0),
        ({"_percent_str": " 42.5% "}, 0.425),
        ({"_percent_str": "100%"}, 1.0),
        ({"_percent_str": "garbage"}, 0.0),
        ({}, 0.0),
    ],
)
def test_safe_percent_computes_from_bytes_or_string(d, expected):
    widget = _widget_no_display()
    assert widget._safe_percent(d) == pytest.approx(expected)
    assert 0.0 <= widget._safe_percent(d) <= 1.0


def test_set_done_marks_bar_and_text():
    widget = _widget_no_display()
    widget.set_done()
    assert widget._progress_bar.value == 1.0
    assert "اكتمل" in widget._info_label.kwargs["text"]


def test_set_error_shows_message():
    widget = _widget_no_display()
    widget.set_error("rate_limited")
    assert widget._info_label.kwargs["text"] == "خطأ: rate_limited"


def test_reset_clears_labels_and_bar():
    widget = _widget_no_display()
    widget.update_progress(
        {"status": "downloading", "downloaded_bytes": 50, "total_bytes": 100}
    )
    widget.reset()
    assert widget._progress_bar.value == 0
    assert "جاهز" in widget._info_label.kwargs["text"]
    assert widget._filename_label.kwargs["text"] == ""


def test_update_progress_downloading_sets_bar_and_labels():
    widget = _widget_no_display()
    widget.update_progress(
        {
            "status": "downloading",
            "downloaded_bytes": 50,
            "total_bytes": 100,
            "_speed_str": "1MiB/s",
            "_eta_str": "00:10",
            "filename": "C:\\vids\\song.mp4",
        }
    )
    assert widget._progress_bar.value == pytest.approx(0.5)
    assert "50.0%" in widget._info_label.kwargs["text"]
    assert "1MiB/s" in widget._info_label.kwargs["text"]
    assert widget._filename_label.kwargs["text"] == "song.mp4"


def test_update_progress_finished_sets_done_text():
    widget = _widget_no_display()
    widget.update_progress({"status": "finished"})
    assert widget._progress_bar.value == 1.0


def test_update_progress_error_sets_error_text():
    widget = _widget_no_display()
    widget.update_progress({"status": "error"})
    assert "خطأ" in widget._info_label.kwargs["text"]