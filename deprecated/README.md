Deprecated helper artifacts that are not required for current runtime.

- `run_checks.bat`: legacy convenience wrapper for `python quick_check.py`.

Legacy email UI (Tkinter) moved here:
- `email_app_v2.py`
- `genimail_ui/`

Legacy tool implementations (kept for compatibility):
- `scanner_app_v4_impl.py`
- `pdf_viewer_impl.py`

Active runtime entrypoints remain at repo root:
- `email_app.py`
- `email_app_qt.py`
- `scanner_app_v4.py`
- `pdf_takeoff_tool.py`
- `pdf_viewer.py` (used by takeoff tool)
