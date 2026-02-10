from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFont, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem

from genimail_qt.constants import EMAIL_LIST_DENSITY_COMFORTABLE, EMAIL_LIST_DENSITY_COMPACT
from genimail_qt.mixins.email_list import CompanyColorDelegate


def _ensure_app():
    return QApplication.instance() or QApplication([])


def _build_index():
    model = QStandardItemModel(1, 1)
    item = QStandardItem("Jan 01\x1fAcme Painter Services\x1fBid Follow Up\x1fCan we schedule a site visit this week?")
    item.setData(
        {
            "isRead": False,
            "from": {"emailAddress": {"address": "estimating@acme.com"}},
            "toRecipients": [],
            "ccRecipients": [],
        },
        Qt.UserRole,
    )
    model.setItem(0, 0, item)
    return model.index(0, 0)


def _make_option(rect):
    option = QStyleOptionViewItem()
    option.rect = rect
    option.state = QStyle.State_Enabled | QStyle.State_Active
    option.showDecorationSelected = True
    return option


def test_delegate_size_hint_is_density_fixed():
    _ensure_app()
    delegate = CompanyColorDelegate()
    index = _build_index()
    option = _make_option(QRect(0, 0, 600, 100))

    delegate.set_density_mode(EMAIL_LIST_DENSITY_COMFORTABLE)
    assert delegate.sizeHint(option, index).height() == 64

    delegate.set_density_mode(EMAIL_LIST_DENSITY_COMPACT)
    assert delegate.sizeHint(option, index).height() == 42


def test_delegate_comfortable_geometry_stays_non_negative_for_narrow_width():
    _ensure_app()
    delegate = CompanyColorDelegate()
    delegate.set_density_mode(EMAIL_LIST_DENSITY_COMFORTABLE)
    row_rect = QRect(24, 0, 86, 64)
    base_font = QFont()
    date_font = delegate._font(base_font, 11)
    date_rect, sender_rect, subject_rect, preview_rect, _ = delegate._compute_comfortable_geometry(
        row_rect, "Jan 01", date_font, "preview line"
    )
    for rect in (date_rect, sender_rect, subject_rect, preview_rect):
        assert rect.width() >= 0
        assert rect.height() >= 0


def test_delegate_compact_geometry_stays_non_negative_for_narrow_width():
    _ensure_app()
    delegate = CompanyColorDelegate()
    delegate.set_density_mode(EMAIL_LIST_DENSITY_COMPACT)
    row_rect = QRect(24, 0, 86, 42)
    base_font = QFont()
    date_font = delegate._font(base_font, 11)
    date_rect, sender_rect, body_rect, _ = delegate._compute_compact_geometry(row_rect, "Jan 01", date_font)
    for rect in (date_rect, sender_rect, body_rect):
        assert rect.width() >= 0
        assert rect.height() >= 0
