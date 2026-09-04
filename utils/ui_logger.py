import queue


class UILogger:
    def __init__(self, q: queue.Queue):
        self._q = q

    def debug(self, msg):
        if not msg.startswith("[debug] "):
            self._q.put(("log", f"[INFO] {msg}"))

    def info(self, msg):
        self._q.put(("log", f"[INFO] {msg}"))

    def warning(self, msg):
        self._q.put(("log", f"[WARN] {msg}"))

    def error(self, msg):
        self._q.put(("log", f"[ERROR] {msg}"))
