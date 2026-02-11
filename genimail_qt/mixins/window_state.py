from genimail.constants import QT_WINDOW_DEFAULT_GEOMETRY, QT_WINDOW_MIN_HEIGHT, QT_WINDOW_MIN_WIDTH


class WindowStateMixin:
    def _restore_window_geometry(self):
        geometry = str(self.config.get("qt_window_geometry", QT_WINDOW_DEFAULT_GEOMETRY))
        try:
            width_text, height_text = geometry.lower().split("x")
            width = max(QT_WINDOW_MIN_WIDTH, int(width_text))
            height = max(QT_WINDOW_MIN_HEIGHT, int(height_text))
        except Exception:
            fallback_width, fallback_height = QT_WINDOW_DEFAULT_GEOMETRY.lower().split("x")
            width = max(QT_WINDOW_MIN_WIDTH, int(fallback_width))
            height = max(QT_WINDOW_MIN_HEIGHT, int(fallback_height))
        self.resize(width, height)

    def closeEvent(self, event):
        self._poll_timer.stop()
        if hasattr(self, "thread_pool"):
            self.thread_pool.waitForDone(2000)
        graph = getattr(self, "graph", None)
        if graph is not None:
            close_graph = getattr(graph, "close", None)
            if callable(close_graph):
                close_graph()
        cache = getattr(self, "cache", None)
        if cache is not None:
            close_cache = getattr(cache, "close", None)
            if callable(close_cache):
                close_cache()
        self.config.set("qt_window_geometry", f"{self.width()}x{self.height()}")
        super().closeEvent(event)

    def _set_status(self, text):
        self.status_lbl.setText(text)


__all__ = ["WindowStateMixin"]
