import os
import shutil
import subprocess
import webbrowser

from PySide6.QtCore import QPoint, QTimer
from PySide6.QtWidgets import QFrame, QLabel, QMessageBox, QVBoxLayout, QWidget

from genimail.constants import INTERNET_DEFAULT_URL

try:
    import win32api
    import win32con
    import win32gui
    import win32process

    HAS_WIN32 = True
except Exception:
    HAS_WIN32 = False


class InternetMixin:
    def _build_internet_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.web_status_lbl = QLabel("External browser mode. Click Internet tab to open.")
        layout.addWidget(self.web_status_lbl)

        self.internet_host_frame = QFrame()
        self.internet_host_frame.setObjectName("internetHostFrame")
        host_layout = QVBoxLayout(self.internet_host_frame)
        host_layout.setContentsMargins(12, 12, 12, 12)
        host_layout.addWidget(QLabel("Browser window will open and align to this region."))
        layout.addWidget(self.internet_host_frame, 1)

        self._internet_browser_url = INTERNET_DEFAULT_URL
        self._internet_browser_path = self._find_browser_executable()
        self._internet_browser_kind = self._detect_browser_kind(self._internet_browser_path)
        self._internet_browser_exe_name = os.path.basename(self._internet_browser_path or "").lower()
        self._internet_browser_proc = None
        self._internet_browser_pid = None
        self._internet_browser_hwnd = None
        self._internet_launch_pending = False

        if not self._internet_browser_path:
            self.web_status_lbl.setText("Chrome not found. Install Chrome to use Internet tab.")
        return tab

    def _on_workspace_tab_changed(self, _index):
        if not hasattr(self, "workspace_tabs") or not hasattr(self, "internet_tab"):
            return
        if self.workspace_tabs.currentWidget() == self.internet_tab:
            self._open_external_browser(self._internet_browser_url, force_new=False)
            self._sync_external_browser_to_target()
            return

    def _on_host_geometry_changed(self):
        if not hasattr(self, "workspace_tabs") or not hasattr(self, "internet_tab"):
            return
        if self.workspace_tabs.currentWidget() != self.internet_tab:
            return
        self._sync_external_browser_to_target()

    def _open_external_browser(self, url, force_new=False):
        if not url:
            return
        if not HAS_WIN32 or os.name != "nt":
            self.web_status_lbl.setText("External browser control is supported on Windows only.")
            return

        if not self._internet_browser_path:
            self.web_status_lbl.setText("Chrome not found. Install Chrome to use Internet tab.")
            QMessageBox.warning(
                self,
                "Chrome Required",
                "Internet tab is configured to use Google Chrome only.\n\nInstall Chrome and try again.",
            )
            return

        hwnd_valid = bool(self._internet_browser_hwnd and win32gui.IsWindow(self._internet_browser_hwnd))
        if not hwnd_valid:
            existing = self._find_browser_window()
            if existing:
                self._internet_browser_hwnd = existing
                hwnd_valid = True

        if force_new or (not hwnd_valid and not self._internet_launch_pending):
            args = self._new_window_args(url)
            self._internet_browser_proc = subprocess.Popen(args)
            self._internet_browser_pid = self._internet_browser_proc.pid
            self._internet_browser_hwnd = None
            self._internet_launch_pending = True
            self.web_status_lbl.setText("Launching browser...")
            self._attach_browser_window(attempt=0)
            return
        if not hwnd_valid and self._internet_launch_pending:
            self.web_status_lbl.setText("Browser launch in progress...")
            return

        # Reuse the currently managed browser window. Do not spawn a new tab/window
        # when the user simply switches back to the Internet tab.
        self._focus_external_browser()
        self._sync_external_browser_to_target()

    def _new_window_args(self, url):
        if self._internet_browser_kind == "firefox":
            return [self._internet_browser_path, "-new-window", url]
        return [self._internet_browser_path, "--new-window", url]

    def _attach_browser_window(self, attempt):
        if not HAS_WIN32 or os.name != "nt":
            return
        hwnd = self._find_browser_window(preferred_pid=self._internet_browser_pid)
        if hwnd:
            self._internet_browser_hwnd = hwnd
            self._internet_launch_pending = False
            self._focus_external_browser()
            self._sync_external_browser_to_target()
            self.web_status_lbl.setText(f"External browser active ({self._internet_browser_kind.title()}).")
            return
        if attempt >= 30:
            self._internet_launch_pending = False
            self.web_status_lbl.setText("Browser opened but could not be attached yet.")
            return
        QTimer.singleShot(150, lambda a=attempt + 1: self._attach_browser_window(a))

    def _find_browser_window(self, preferred_pid=None):
        if not HAS_WIN32:
            return None
        preferred = []
        matches = []
        class_map = {
            "firefox": {"MozillaWindowClass"},
            "edge": {"Chrome_WidgetWin_1"},
            "chromium": {"Chrome_WidgetWin_1"},
            "brave": {"Chrome_WidgetWin_1"},
        }
        allowed_classes = class_map.get(self._internet_browser_kind, set())

        def callback(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = (win32gui.GetWindowText(hwnd) or "").strip()
            if not title:
                return True
            class_name = (win32gui.GetClassName(hwnd) or "").strip()
            if allowed_classes and class_name not in allowed_classes:
                return True
            _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
            exe_name = self._window_exe_name(window_pid)
            if self._internet_browser_exe_name and exe_name and exe_name != self._internet_browser_exe_name:
                return True
            if preferred_pid and window_pid == preferred_pid:
                preferred.append(hwnd)
                return True
            matches.append(hwnd)
            return True

        win32gui.EnumWindows(callback, None)
        if preferred:
            return preferred[0]
        return matches[0] if matches else None

    @staticmethod
    def _window_exe_name(pid):
        if not HAS_WIN32 or not pid:
            return ""
        process_handle = None
        try:
            query_flag = getattr(win32con, "PROCESS_QUERY_LIMITED_INFORMATION", 0x1000)
            vm_read_flag = getattr(win32con, "PROCESS_VM_READ", 0x0010)
            process_handle = win32api.OpenProcess(query_flag | vm_read_flag, False, pid)
            path = win32process.GetModuleFileNameEx(process_handle, 0) or ""
            return os.path.basename(path).lower()
        except Exception:
            return ""
        finally:
            if process_handle:
                try:
                    win32api.CloseHandle(process_handle)
                except Exception:
                    pass

    def _sync_external_browser_to_target(self):
        if not HAS_WIN32 or os.name != "nt":
            return
        hwnd = self._internet_browser_hwnd
        if not hwnd or not win32gui.IsWindow(hwnd):
            return
        if self.workspace_tabs.currentWidget() != self.internet_tab:
            return
        if self.isMinimized():
            self._minimize_external_browser()
            return
        top_left = self.internet_host_frame.mapToGlobal(QPoint(0, 0))
        rect = self.internet_host_frame.rect()
        width = max(320, rect.width())
        height = max(240, rect.height())
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOP,
                int(top_left.x()),
                int(top_left.y()),
                int(width),
                int(height),
                win32con.SWP_SHOWWINDOW,
            )
        except Exception:
            pass

    def _focus_external_browser(self):
        if not HAS_WIN32 or os.name != "nt":
            return
        hwnd = self._internet_browser_hwnd
        if not hwnd or not win32gui.IsWindow(hwnd):
            self._open_external_browser(self._internet_browser_url, force_new=False)
            return
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def _minimize_external_browser(self):
        if not HAS_WIN32 or os.name != "nt":
            return
        hwnd = self._internet_browser_hwnd
        if not hwnd or not win32gui.IsWindow(hwnd):
            return
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        except Exception:
            pass

    @staticmethod
    def _detect_browser_kind(path):
        lowered = (path or "").lower()
        if "firefox" in lowered:
            return "firefox"
        if "msedge" in lowered:
            return "edge"
        if "brave" in lowered:
            return "brave"
        return "chromium"

    @staticmethod
    def _find_browser_executable():
        env_paths = [
            shutil.which("chrome"),
        ]
        hardcoded = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for candidate in [*env_paths, *hardcoded]:
            if candidate and os.path.exists(candidate):
                return candidate
        return None


__all__ = ["InternetMixin"]
