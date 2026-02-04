# Repository Guidelines

## Project Structure & Module Organization
- `scanner_app.py` contains the Windows WIA scanner desktop app (Tkinter + Pillow).
- `email_app.py` contains the Outlook/Hotmail desktop client (MSAL + Microsoft Graph + Tkinter).
- Runtime data lives beside the apps:
  - `scans/` for generated PNG scan pages
  - `pdf/` for generated PDF exports
  - `email_config/` for local config, token cache, and SQLite cache
- Helper launchers: `run.bat` (scanner) and `run_email.bat` (email hub).
- The project is currently a flat layout; keep new modules small and app-specific unless a shared utility is clearly reusable.

## Build, Test, and Development Commands
- Create/activate virtual env (PowerShell):
  - `python -m venv .venv`
  - `.\.venv\Scripts\Activate.ps1`
- Install dependencies:
  - `pip install pillow pywin32 msal requests winotify`
  - Optional HTML view: `pip install tkinterweb`
- Run scanner app: `python scanner_app.py` or `run.bat`
- Run email app: `python email_app.py` or `run_email.bat`

## Coding Style & Naming Conventions
- Follow Python 3 + PEP 8 with 4-space indentation.
- Naming:
  - Classes: `PascalCase` (e.g., `ScannerApp`, `EmailCache`)
  - Functions/variables: `snake_case`
  - Constants: `UPPER_SNAKE_CASE`
- Keep UI assembly in `_build_*` methods and user actions in `_on_*` callbacks.
- For background work, use threads and marshal UI updates back with `root.after(...)`.

## Testing Guidelines
- No formal automated test suite exists yet; use targeted manual smoke tests for each change.
- Minimum manual checks:
  - Scanner: scan, rotate, save as PDF/PNG/JPEG.
  - Email: sign-in, folder load, message preview, attachment open/save.
- If adding pure logic helpers, add `pytest` tests under `tests/` using `test_*.py` naming.

## Commit & Pull Request Guidelines
- This folder currently has no visible Git history; use Conventional Commit style:
  - `feat: add attachment size formatter`
  - `fix: prevent UI freeze during scan`
- Keep commits focused and reversible.
- PRs should include: purpose, user-visible impact, manual test steps/results, and screenshots for UI changes.

## Security & Configuration Tips
- Do not commit personal/runtime artifacts from `email_config/`, `scans/`, or `pdf/`.
- Treat `token_cache.json`, `email_cache.db*`, and scanned documents as sensitive local data.
