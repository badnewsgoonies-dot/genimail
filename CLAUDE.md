# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GENImail is a Windows-only desktop hub combining email, internet browsing, PDF viewing, docs/templates, and scanning in one PySide6 application. It integrates with Outlook/Hotmail via Microsoft Graph API using MSAL device code flow.

**Domain**: Construction painting business — email, quotes, PDF plan takeoffs (paint area calculations), scanner integration, company-domain filtering with color-coded labels.

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

### Layer Separation (strict — no cross-layer imports)

- **`genimail/`** — Core business logic (pure Python, **no Qt imports allowed**)
  - `domain/` — Business helpers: HTML cleanup, quote generation, length parsing (ft/in/mm/cm/m)
  - `infra/` — Infrastructure: Graph API client (`graph_client.py`), config store, SQLite cache store (725 lines, delta sync)
  - `services/` — Sync orchestration (`mail_sync.py`)
  - `browser/` — WebView2 COM runtime helpers (runtime, navigation, host)
  - `errors.py` — Error hierarchy: `ProjectError` → `ValidationError`, `ExternalServiceError`
  - `constants.py` — All magic numbers: API config, timeouts, measurements, email fetch limits
  - `paths.py` — Centralized path definitions for config, cache, PDFs, quotes

- **`genimail_qt/`** — PySide6 UI layer (imports `genimail` one-way only)
  - `window.py` — Main window class (`GeniMailQtWindow`), composes 13 mixins
  - `mixins/` — Feature mixins (see composition below)
  - `workers.py` — `Worker` (QRunnable) + `WorkerSignals` for background threading
  - `helpers/` — `toaster.py` (toast notifications), `worker_manager.py` (QThreadPool wrapper)
  - `dialogs.py`, `compose_dialog.py`, `company_manager_dialog.py`, `company_tab_manager_dialog.py`
  - `theme.py` — All styling (`APP_STYLE` stylesheet; no Qt Designer files)
  - `constants.py` — UI-specific constants: layout margins, icon strings, regex patterns, toast config
  - `takeoff_engine.py` — Paint area calculation for construction takeoffs
  - `webview_utils.py`, `webview_page.py` — WebEngine helpers (JS console filtering, custom page)
  - `pdf_graphics_view.py` — Custom QGraphicsView for PDF rendering with measurement overlays

- **Standalone apps** (top-level):
  - `email_app.py` → `email_app_qt.py` — Main application entrypoint
  - `scanner_app_v4.py` — Windows WIA scanner (Tkinter + Pillow + pywin32)
  - `pdf_viewer.py` — Standalone PDF viewer
  - `pdf_takeoff_tool.py` — Click-to-measure PDF tool

- **`deprecated/`** — Legacy Tkinter email UI (no longer active, do not modify)

### Main Window Composition

`GeniMailQtWindow` uses mixin inheritance to compose features. The MRO order matters:

```python
class GeniMailQtWindow(
    LayoutMixin,           # _build_ui: tabs (Internet, Email, PDF, Docs) + top bar
    InternetMixin,         # WebView2 browser tab
    EmailUiMixin,          # Email workspace layout + preview panel
    PdfUiMixin,            # PDF viewer panel
    DocsMixin,             # Templates/docs workspace
    WindowStateMixin,      # Window geometry persistence
    AuthPollMixin,         # MSAL auth + sync polling + folder resolution
    CompanyMixin,          # Company folder filtering + tab management
    CompanySearchMixin,    # Company domain search integration
    EmailListMixin,        # Message list rendering + folder selection + preview
    EmailAttachmentMixin,  # Attachment display and management
    ComposeMixin,          # Email composition dialog integration
    PdfMixin,              # PDF viewing and rendering
    QMainWindow,
):
```

Mixins use `hasattr(self, "method_name")` checks for optional cross-mixin callbacks, avoiding hard coupling.

### Data Flow

1. **Auth**: MSAL device code flow → token stored in `email_config/`
2. **Sync**: Graph API → delta sync → SQLite cache (`email_config/email_cache.db`)
3. **UI**: Cache queries → filtered message list → preview pane

### Threading Model

- `QThreadPool` capped at 3 workers (`QT_THREAD_POOL_MAX_WORKERS`)
- `Worker(QRunnable)` wraps any function; emits `WorkerSignals.result` or `WorkerSignals.error`
- `WorkerManager` handles submission + default error callback
- Never call Qt widgets from worker threads — always marshal through signals

### Error Hierarchy

```
ProjectError (base, genimail/errors.py)
├── ValidationError
├── ExternalServiceError
│   └── BrowserRuntimeError (genimail/browser/errors.py)
│       ├── BrowserFeatureUnavailableError
│       ├── BrowserNavigationError
│       └── BrowserDownloadError
```

## Coding Conventions

- UI assembly in `_build_*` methods (e.g., `_build_toolbar`, `_build_sidebar`)
- User actions in `_on_*` callbacks (e.g., `_on_send_clicked`, `_on_folder_selected`)
- All magic numbers go in `genimail/constants.py` or `genimail_qt/constants.py` — never inline
- Naming: classes `PascalCase`, functions/variables `snake_case`, constants `UPPER_SNAKE_CASE`
- Commit style: Conventional Commits (`feat:`, `fix:`, `refactor:`, `chore:`, `docs:`)
- Graph client soft-imports `msal` and `requests` with try/except (graceful degradation)

## Testing

- Tests live in `tests/` with `test_*.py` naming; no `conftest.py` or shared fixtures
- `quick_check.py` validates: py_compile on 57 curated files → import smoke test → pytest
- Tests are simple: direct function imports + assertions, monkeypatching for mixin isolation
- No mock framework — tests use plain stubs and attribute patching

## Local Data (Git-Ignored)

- `email_config/` — Tokens, app config, SQLite cache
- `scans/` — Scanner output PNGs
- `pdf/` — Generated PDFs
- `quotes/` — Quote outputs
