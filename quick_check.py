import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PY_FILES = [
    "email_app_v2.py",
    "pdf_viewer.py",
    "scanner_app_v4.py",
    "genimail/paths.py",
    "genimail/constants.py",
    "genimail/ui/theme.py",
    "genimail/ui/widgets.py",
    "genimail/ui/tabs.py",
    "genimail/ui/dialogs.py",
    "genimail/ui/splash.py",
    "genimail/domain/helpers.py",
    "genimail/domain/quotes.py",
    "genimail/infra/cache_store.py",
    "genimail/infra/graph_client.py",
    "genimail/infra/config_store.py",
    "genimail/services/mail_sync.py",
]


def run(cmd):
    print("> " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main():
    run([sys.executable, "-m", "py_compile", *PY_FILES])
    run([sys.executable, "-c", "import email_app_v2, pdf_viewer, scanner_app_v4; print('imports ok')"])
    run([sys.executable, "-m", "pytest", "-q"])
    print("All automated checks passed.")


if __name__ == "__main__":
    main()
