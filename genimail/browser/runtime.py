from dataclasses import dataclass
from enum import Enum
import importlib

from genimail.constants import BROWSER_RUNTIME_INSTALL_URL


class BrowserRuntimeStatus(str, Enum):
    READY = "READY"
    MISSING_RUNTIME = "MISSING_RUNTIME"
    INIT_FAILED = "INIT_FAILED"


@dataclass(frozen=True)
class BrowserRuntimeInfo:
    status: BrowserRuntimeStatus
    detail: str
    engine: str = "webview2"


def _resolve_have_runtime():
    errors = []
    for module_name in ("tkwebview2", "tkwebview2.tkwebview2"):
        try:
            module = importlib.import_module(module_name)
            candidate = getattr(module, "have_runtime", None)
            if callable(candidate):
                return candidate
            errors.append(f"{module_name}.have_runtime not found")
        except Exception as exc:
            errors.append(f"{module_name}: {exc}")
    raise RuntimeError("; ".join(errors))


def detect_browser_runtime() -> BrowserRuntimeInfo:
    try:
        have_runtime = _resolve_have_runtime()
    except Exception as exc:
        return BrowserRuntimeInfo(
            status=BrowserRuntimeStatus.INIT_FAILED,
            detail=f"Browser dependency missing: {exc}",
        )

    try:
        runtime_ready = bool(have_runtime())
    except Exception as exc:
        return BrowserRuntimeInfo(
            status=BrowserRuntimeStatus.INIT_FAILED,
            detail=f"Runtime check failed: {exc}",
        )

    if runtime_ready:
        return BrowserRuntimeInfo(
            status=BrowserRuntimeStatus.READY,
            detail="WebView2 runtime detected.",
        )

    return BrowserRuntimeInfo(
        status=BrowserRuntimeStatus.MISSING_RUNTIME,
        detail=(
            "Microsoft Edge WebView2 Runtime is missing. "
            f"Install it from: {BROWSER_RUNTIME_INSTALL_URL}"
        ),
    )
