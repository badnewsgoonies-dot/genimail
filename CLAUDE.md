# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GENImail is a Windows-only desktop hub combining email, internet browsing, PDF viewing, docs/templates, and scanning in one PySide6 application. It integrates with Outlook/Hotmail via Microsoft Graph API using MSAL device code flow.

**Tech stack**: Python 3.11+, PySide6 (QtWidgets + QtWebEngine), MSAL + requests (Graph API), PyMuPDF (PDF rendering), pywin32 (WIA scanner + COM), Shapely (takeoff geometry), Pillow, SQLite.

## Build & Development Commands

```powershell
# Setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run the main app
python email_app.py          # or: run_email.bat

# Validate before release (py_compile + import smoke + pytest)
python quick_check.py

# Run tests
python -m pytest -q

# Run a single test file
python -m pytest tests/test_email_helpers.py -v

# Run a specific test function
python -m pytest tests/test_email_helpers.py::test_function_name -v
```

No linter or formatter config exists; follow PEP 8 with 4-space indentation.

## Architecture

### Layer Separation

- **`genimail/`** - Core business logic (pure Python, **no Qt imports**)
  - `domain/` - Business helpers: HTML cleanup, cloud link detection, quote generation
  - `infra/` - Infrastructure: Graph API client, config store, SQLite cache store
  - `services/` - Sync orchestration (mail_sync)
  - `browser/` - WebView2 COM runtime helpers (downloads, navigation, host, errors)

- **`genimail_qt/`** - PySide6 UI layer
  - `window.py` - Main window class (`GeniMailQtWindow`)
  - `mixins/` - Feature mixins that compose the main window (see below)
  - `workers.py` - QRunnable workers for background tasks
  - `dialogs.py`, `compose_dialog.py`, `company_manager_dialog.py` - Modal dialogs
  - `theme.py` - All styling/theming (no Qt Designer files; UI is built programmatically)
  - `takeoff_engine.py` - Paint area calculation for construction takeoffs

- **Standalone apps:**
  - `email_app.py` → `email_app_qt.py` - Main application entrypoint
  - `scanner_app_v4.py` - Windows WIA scanner app (Tkinter + Pillow + pywin32)
  - `pdf_viewer.py` - Standalone PDF viewer
  - `pdf_takeoff_tool.py` - Click-to-measure PDF tool

- **`deprecated/`** - Legacy Tkinter email UI (no longer active, do not modify)

### Main Window Composition

`GeniMailQtWindow` uses mixin inheritance to compose features:
- `ToastMixin`, `LayoutMixin` - Core UI infrastructure
- `WindowStateMixin` - Window state persistence
- `AuthPollMixin` - MSAL device code authentication
- `EmailListMixin`, `EmailUiMixin`, `EmailAttachmentMixin` - Email workspace
- `InternetMixin` - Browser workspace
- `PdfMixin`, `PdfUiMixin` - PDF viewing workspace
- `DocsMixin` - Templates workspace
- `CompanyMixin` - Company domain filtering
- `ComposeMixin` - Email composition
- `WorkerMixin` - Background task management

### Data Flow

1. **Auth**: MSAL device code flow → token stored in `email_config/`
2. **Sync**: Graph API → delta sync → SQLite cache (`email_config/email_cache.db`)
3. **UI**: Cache queries → filtered message list → preview pane

## Coding Conventions

- UI assembly in `_build_*` methods (e.g., `_build_toolbar`, `_build_sidebar`)
- User actions in `_on_*` callbacks (e.g., `_on_send_clicked`, `_on_folder_selected`)
- Background work via `QThreadPool` + `QRunnable`; marshal UI updates back to main thread with Qt signals. Never call Qt widgets directly from worker threads.
- Naming: classes `PascalCase`, functions/variables `snake_case`, constants `UPPER_SNAKE_CASE`
- Commit style: Conventional Commits (`feat:`, `fix:`, `refactor:`, `chore:`, `docs:`)

## Local Data (Git-Ignored)

- `email_config/` - Tokens, app config, SQLite cache
- `scans/` - Scanner output PNGs
- `pdf/` - Generated PDFs
