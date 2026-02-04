import ctypes
import threading
from dataclasses import dataclass


COINIT_APARTMENTTHREADED = 0x2
RPC_E_CHANGED_MODE = -2147417850  # 0x80010106


@dataclass(frozen=True)
class ComRuntimeStatus:
    ready: bool
    detail: str


_status_lock = threading.Lock()
_cached_status = None


def ensure_sta_apartment() -> ComRuntimeStatus:
    """Initialize current thread COM apartment as STA once per process."""
    global _cached_status
    with _status_lock:
        if _cached_status is not None:
            return _cached_status

        try:
            co_initialize_ex = ctypes.windll.ole32.CoInitializeEx
            co_initialize_ex.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            co_initialize_ex.restype = ctypes.c_long
        except Exception as exc:
            _cached_status = ComRuntimeStatus(
                ready=False,
                detail=f"COM initialization API unavailable: {exc}",
            )
            return _cached_status

        hr = co_initialize_ex(None, COINIT_APARTMENTTHREADED)
        if hr == RPC_E_CHANGED_MODE:
            _cached_status = ComRuntimeStatus(
                ready=False,
                detail=(
                    "Thread COM mode is already set to a non-STA mode "
                    "(RPC_E_CHANGED_MODE)."
                ),
            )
            return _cached_status

        _cached_status = ComRuntimeStatus(
            ready=True,
            detail="STA COM apartment ready.",
        )
        return _cached_status
