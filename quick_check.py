import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PY_FILES = [
    "email_app.py",
    "email_app_qt.py",
    "pdf_takeoff_tool.py",
    "pdf_viewer.py",
    "scanner_app_v4.py",
    "genimail/paths.py",
    "genimail/constants.py",
    "genimail/com_runtime.py",
    "genimail/errors.py",
    "genimail/browser/__init__.py",
    "genimail/browser/errors.py",
    "genimail/browser/runtime.py",
    "genimail/browser/navigation.py",
    "genimail/browser/host.py",
    "genimail/domain/helpers.py",
    "genimail/domain/quotes.py",
    "genimail/infra/document_store.py",
    "genimail/infra/cache_store.py",
    "genimail/infra/graph_client.py",
    "genimail/infra/config_store.py",
    "genimail/services/mail_sync.py",
    "genimail_qt/__init__.py",
    "genimail_qt/constants.py",
    "genimail_qt/helpers/__init__.py",
    "genimail_qt/helpers/toaster.py",
    "genimail_qt/helpers/worker_manager.py",
    "genimail_qt/theme.py",
    "genimail_qt/workers.py",
    "genimail_qt/dialogs.py",
    "genimail_qt/company_manager_dialog.py",
    "genimail_qt/company_tab_manager_dialog.py",
    "genimail_qt/webview_utils.py",
    "genimail_qt/webview_page.py",
    "genimail_qt/pdf_graphics_view.py",
    "genimail_qt/takeoff_engine.py",
    "genimail_qt/window.py",
    "genimail_qt/mixins/attachments.py",
    "genimail_qt/mixins/auth.py",
    "genimail_qt/mixins/company.py",
    "genimail_qt/mixins/compose.py",
    "genimail_qt/mixins/docs.py",
    "genimail_qt/mixins/email_company_search.py",
    "genimail_qt/mixins/email_list.py",
    "genimail_qt/mixins/email_ui.py",
    "genimail_qt/mixins/internet.py",
    "genimail_qt/mixins/layout.py",
    "genimail_qt/mixins/pdf.py",
    "genimail_qt/mixins/pdf_ui.py",
    "genimail_qt/mixins/window_state.py",
]


def run(cmd):
    print("> " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main():
    run([sys.executable, "-m", "py_compile", *PY_FILES])
    run([sys.executable, "-c", "import email_app, pdf_viewer, scanner_app_v4; print('imports ok')"])
    run([sys.executable, "-m", "pytest", "-q"])
    print("All automated checks passed.")


if __name__ == "__main__":
    main()
