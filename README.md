# GENImail

Modular Windows desktop hub for email, PDF review, and scanning.

- Outlook/Hotmail integration via Microsoft Graph + MSAL device code flow
- Warm, paper-style Tkinter UI
- Embedded PDF viewer tab
- Integrated scanner tab
- Local SQLite cache + delta sync

## What It Does

GENImail combines three daily workflows in one app:

1. **Email**: read, search, preview, reply/forward, download attachments
2. **PDF**: inspect and measure PDF documents in-app
3. **Scan**: run scanner actions from the Scan tab

## Tech Stack

- Python 3.11+
- Tkinter
- Microsoft Graph API (`msal`, `requests`)
- Pillow + pywin32 (scanner paths)
- PyMuPDF (PDF rendering)
- SQLite (local cache)

## Quick Start (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python email_app_v2.py
```

Or run:

```bat
run_email.bat
```

## Project Layout

- `email_app_v2.py` — main shell and orchestration
- `genimail/`
  - `domain/` — business helpers (HTML cleanup, quote generation)
  - `infra/` — Graph client, config store, cache store
  - `services/` — sync orchestration
  - `ui/` — theme, widgets, tabs, dialogs, splash
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
- iOS/iPadOS are not target runtime environments for this codebase.
