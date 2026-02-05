# GENImail

Modular Windows desktop hub for email, internet, PDF review, docs/templates, and scanning.

- Outlook/Hotmail integration via Microsoft Graph + MSAL device code flow
- Modern PySide6 multi-workspace shell
- Dedicated Internet + PDF Viewer + Docs/Templates workspaces
- Scanner available as a persistent utility action
- Local SQLite cache + delta sync

## What It Does

GENImail combines daily workflows in one app:

1. **Email**: read, search, preview, reply/forward, download attachments
   - Company-domain filtering + company manager labels
   - Linked cloud PDF detection (Google Drive/Dropbox/OneDrive style links)
   - One-click open for single cloud link + local cache reuse
2. **Internet**: open and navigate web pages in-app
3. **PDF**: open multiple PDFs in dedicated tabs
4. **Docs/Templates**: create quote drafts from templates
   - Takeoff beta fields (linear/height/openings/coats) for paint-area math
   - Launch dedicated click-to-measure tool
5. **Scan**: launch scanner tools from the top utility action

## Tech Stack

- Python 3.11+
- PySide6 (`QtWidgets` + `QtWebEngine`)
- Microsoft Graph API (`msal`, `requests`)
- Embedded browser/PDF surfaces via Qt WebEngine
- Pillow + pywin32 (scanner paths)
- PyMuPDF (PDF rendering)
- Shapely (advanced takeoff geometry)
- SQLite (local cache)

## Quick Start (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python email_app.py
```

Or run:

```bat
run_email.bat
```

## Project Layout

- `email_app_qt.py` — PySide6 application entrypoint
- `email_app.py` — stable launcher alias (recommended)
- `genimail/`
  - `domain/` — business helpers (HTML cleanup, quote generation)
  - `infra/` — Graph client, config store, cache store
  - `services/` — sync orchestration
  - `ui/` — theme, widgets, tabs, dialogs, splash
- `genimail_qt/` — Qt shell, threading helpers, and Qt theme
- `scanner_app_v4.py` — scanner implementation
- `pdf_viewer.py` — PDF viewer implementation
- `tests/` — regression and helper tests
- `quick_check.py` — compile/import/pytest gate

## Validate Before Release

```powershell
python quick_check.py
```

This runs:

- `py_compile` checks
- import smoke checks
- `pytest` suite

## Security / Local Data

The following contain local runtime data and are git-ignored:

- `email_config/` (token cache, app config, SQLite cache)
- `scans/`
- `pdf/`

## Notes

- This is a Windows-focused desktop app.
- Qt WebEngine ships through the PySide6 dependency path.
- iOS/iPadOS are not target runtime environments for this codebase.
