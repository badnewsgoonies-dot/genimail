# Copilot Instructions for GENImail

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

# Run all tests
python -m pytest -q

# Run a single test file
python -m pytest tests/test_email_helpers.py -v

# Run a specific test function
python -m pytest tests/test_email_helpers.py::test_function_name -v
```

## Architecture

### Layer Separation

- **`genimail/`** - Core business logic (pure Python, no Qt dependencies)
  - `domain/` - Business helpers: HTML cleanup, cloud link detection, quote generation
  - `infra/` - Infrastructure: Graph API client, config store, SQLite cache store
  - `services/` - Sync orchestration (mail_sync)
  - `browser/` - WebView2 COM runtime helpers

- **`genimail_qt/`** - PySide6 UI layer
  - `window.py` - Main window class (`GeniMailQtWindow`)
  - `mixins/` - Feature mixins that compose the main window
  - `workers.py` - QRunnable workers for background tasks
  - `dialogs.py` - Modal dialogs

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

### Standalone Apps

- `scanner_app_v4.py` - Windows WIA scanner app (Tkinter + Pillow + pywin32)
- `pdf_viewer.py` - Standalone PDF viewer
- `pdf_takeoff_tool.py` - Click-to-measure PDF tool for construction takeoffs

## Coding Conventions

### Method Naming

- UI assembly: `_build_*` methods (e.g., `_build_toolbar`, `_build_sidebar`)
- User actions: `_on_*` callbacks (e.g., `_on_send_clicked`, `_on_folder_selected`)

### Background Work

- Use `QThreadPool` + `QRunnable` for background tasks
- Marshal UI updates back to main thread with Qt signals
- Never call Qt widgets directly from worker threads

### Naming

- Classes: `PascalCase` (e.g., `ScannerApp`, `EmailCache`)
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`

## Local Data (Git-Ignored)

These directories contain runtime data and should never be committed:

- `email_config/` - Tokens, app config, SQLite cache
- `scans/` - Scanner output PNGs
- `pdf/` - Generated PDFs
