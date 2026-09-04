import queue

from utils.ui_logger import UILogger


def _drain(q):
    out = []
    while True:
        try:
            out.append(q.get_nowait())
        except queue.Empty:
            return out


def test_info_emits_log_event():
    q = queue.Queue()
    UILogger(q).info("starting")
    assert _drain(q) == [("log", "[INFO] starting")]


def test_warning_prefixes_warn():
    q = queue.Queue()
    UILogger(q).warning("slow")
    assert _drain(q) == [("log", "[WARN] slow")]


def test_error_prefixes_error():
    q = queue.Queue()
    UILogger(q).error("boom")
    assert _drain(q) == [("log", "[ERROR] boom")]


def test_debug_emits_info_for_non_debug_message():
    q = queue.Queue()
    UILogger(q).debug("extracting formats")
    assert _drain(q) == [("log", "[INFO] extracting formats")]


def test_debug_suppresses_already_prefixed_debug_message():
    q = queue.Queue()
    UILogger(q).debug("[debug] internal")
    assert _drain(q) == []