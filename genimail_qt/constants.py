import re

JS_CONSOLE_DEBUG_ENV = "GENIMAIL_DEBUG_JS_CONSOLE"

COMPANY_COLLAPSE_ICON_COLLAPSED = "▶"
COMPANY_COLLAPSE_ICON_EXPANDED = "▼"
COMPANY_STAR_ICON = "★"

JS_NOISE_PATTERNS = (
    "was preloaded using link preload but not used",
    "permissions policy violation: unload is not allowed",
    "error with permissions-policy header: unrecognized feature",
    "document-policy http header: unrecognized document policy feature name",
    "unable to find performance entry for rtb request",
    "this app error id:",
    "sj_evt is not defined",
)

LOCAL_JS_SOURCE_PREFIXES = (
    "about:",
    "data:",
    "file:",
    "qrc:",
)

CID_SRC_PATTERN = re.compile(r"cid:([^\"'>\s)]+)", re.IGNORECASE)

ROOT_LAYOUT_MARGINS = (0, 0, 0, 0)
ROOT_LAYOUT_SPACING = 0
TOP_BAR_MARGINS = (12, 8, 12, 8)
TOP_BAR_SPACING = 8
TOP_BAR_TITLE_SPACING = 12

TOAST_LAYOUT_MARGINS = (10, 6, 10, 6)
TOAST_LAYOUT_SPACING = 6
TOAST_MARGIN_PX = 16
TOAST_TOP_OFFSET_PX = 8
TOAST_DEFAULT_DURATION_MS = 2200

COMPOSE_DIALOG_SIZE = (780, 620)

__all__ = [
    "CID_SRC_PATTERN",
    "COMPANY_COLLAPSE_ICON_COLLAPSED",
    "COMPANY_COLLAPSE_ICON_EXPANDED",
    "COMPANY_STAR_ICON",
    "COMPOSE_DIALOG_SIZE",
    "JS_CONSOLE_DEBUG_ENV",
    "JS_NOISE_PATTERNS",
    "LOCAL_JS_SOURCE_PREFIXES",
    "ROOT_LAYOUT_MARGINS",
    "ROOT_LAYOUT_SPACING",
    "TOAST_DEFAULT_DURATION_MS",
    "TOAST_LAYOUT_MARGINS",
    "TOAST_LAYOUT_SPACING",
    "TOAST_MARGIN_PX",
    "TOAST_TOP_OFFSET_PX",
    "TOP_BAR_MARGINS",
    "TOP_BAR_SPACING",
    "TOP_BAR_TITLE_SPACING",
]
