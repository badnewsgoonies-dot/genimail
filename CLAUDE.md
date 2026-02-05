# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GENImail is a Windows desktop hub combining email, internet browsing, PDF viewing, docs/templates, and scanning in one PySide6 application. It integrates with Outlook/Hotmail via Microsoft Graph API using MSAL device code flow.

## Build & Development Commands

```powershell
# Setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run the main app
python email_app.py

# Validate before release (compile checks + imports + pytest)
python quick_check.py

# Run tests
python -m pytest -q

# Run a single test
python -m pytest tests/test_email_helpers.py -v
```

## Architecture

### Package Structure

- **`genimail/`** - Core business logic (pure Python, no Qt)
  - `domain/` - Business helpers: HTML cleanup, cloud link detection, quote generation
  - `infra/` - Infrastructure: Graph API client, config store, SQLite cache store
  - `services/` - Sync orchestration (mail_sync)
  - `browser/` - WebView2 COM runtime helpers (downloads, navigation, host)

- **`genimail_qt/`** - PySide6 UI layer
  - `window.py` - Main window class (`GeniMailQtWindow`)
  - `mixins/` - Feature mixins that compose the main window (auth, email, pdf, internet, compose, etc.)
  - `workers.py` - QRunnable workers for background tasks
  - `dialogs.py`, `compose_dialog.py`, `company_manager_dialog.py` - Modal dialogs
  - `takeoff_engine.py` - Paint area calculation for construction takeoffs

- **Standalone apps:**
  - `email_app.py` / `email_app_qt.py` - Main application entrypoint
  - `scanner_app_v4.py` - Windows WIA scanner app
  - `pdf_viewer.py` - Standalone PDF viewer
  - `pdf_takeoff_tool.py` - Click-to-measure PDF tool

### Main Window Composition

`GeniMailQtWindow` uses mixin inheritance to compose features:
- `ToastMixin`, `LayoutMixin` - Core UI infrastructure
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

- UI assembly in `_build_*` methods
- User actions in `_on_*` callbacks
- Background work via `QThreadPool` + `QRunnable`, marshal UI updates with signals
- Follow PEP 8, 4-space indentation

## Local Data (Git-Ignored)

- `email_config/` - Tokens, app config, SQLite cache
- `scans/` - Scanner output PNGs
- `pdf/` - Generated PDFs
