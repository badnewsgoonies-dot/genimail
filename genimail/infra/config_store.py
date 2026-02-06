import json
import os

from genimail.constants import TAKEOFF_DEFAULT_WALL_HEIGHT
from genimail.paths import CONFIG_DIR, CONFIG_FILE, DEFAULT_QUOTE_TEMPLATE_FILE, QUOTE_DIR


class Config:
    """Persistent configuration manager."""

    def __init__(self):
        self.load_error = None
        self.data = {
            "companies": {},
            "company_colors": {},
            "company_collapsed": False,
            "company_favorites": [],
            "company_hidden": [],
            "company_order": [],
            "client_id": "",
            "browser_engine": "webview2",
            "pdf_calibration": {},
            "window_geometry": "1100x700",
            "quote_template_path": DEFAULT_QUOTE_TEMPLATE_FILE,
            "quote_output_dir": QUOTE_DIR,
            "takeoff_default_wall_height": TAKEOFF_DEFAULT_WALL_HEIGHT,
            "door_finder_enabled": True,
        }
        self.load()

    def load(self):
        self.load_error = None
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if not isinstance(saved, dict):
                    raise ValueError("Config payload must be a JSON object.")
                self.data.update(saved)
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                self.load_error = str(exc)

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()
