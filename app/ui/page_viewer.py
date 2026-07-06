from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

_ACCENT_SOFT = QColor(108, 140, 255, 70)
_NAV_BUTTON_STYLE = """
    QPushButton {
        background: rgba(36, 37, 49, 190);
        color: white;
        border: 1px solid rgba(255, 255, 255, 60);
        border-radius: 21px;
        font-size: 20px;
        font-weight: 600;
    }
    QPushButton:hover { background: rgba(108, 140, 255, 220); }
    QPushButton:disabled { background: rgba(36, 37, 49, 90); color: rgba(255, 255, 255, 60); }
"""

_MIN_ZOOM = 0.05
_MAX_ZOOM = 12.0
_DRAG_THRESHOLD = 4  # px of mouse movement before a click becomes a drag


def _np_to_qpixmap(array: np.ndarray) -> QPixmap:
    array = np.ascontiguousarray(array)
    h, w, _ = array.shape
    image = QImage(array.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(image.copy())


class _Canvas(QLabel):
    """Plain QLabel showing a (possibly scaled) QPixmap. Handles its own
    wheel-zoom, drag-to-pan/drag-the-compare-slider, and click-to-select -
    all forwarded to the owning PageViewer, which does the actual pixmap
    composition and scrollbar math.

    This replaces an earlier QGraphicsView-based canvas: on at least one
    real user machine, that QGraphicsView painted nothing at all (solid
    black, despite the scene/transform/visibility all being internally
    correct - panning still worked, so it wasn't hung, just never actually
    drawing) while this plain QLabel approach is what the app used
    (correctly) before zoom/pan/click-select existed at all.
    """

    def __init__(self, viewer: "PageViewer") -> None:
        super().__init__()
        self._viewer = viewer
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._dragging = False
        self._dragged_past_threshold = False
        self._press_pos = QPointF()
        self._h_start = 0
        self._v_start = 0

    def wheelEvent(self, event) -> None:  # noqa: N802 (Qt override)
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._viewer._zoom_at(factor, event.position())
        event.accept()

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._dragged_past_threshold = False
            self._press_pos = event.position()
            hbar, vbar = self._viewer._scrollbars()
            self._h_start = hbar.value()
            self._v_start = vbar.value()
            if self._viewer.mode == "compare":
                self._viewer._slider_at(event.position())
            else:
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if self._dragging:
            delta = event.position() - self._press_pos
            if delta.manhattanLength() > _DRAG_THRESHOLD:
                self._dragged_past_threshold = True
            if self._viewer.mode == "compare":
                self._viewer._slider_at(event.position())
            else:
                hbar, vbar = self._viewer._scrollbars()
                hbar.setValue(int(self._h_start - delta.x()))
                vbar.setValue(int(self._v_start - delta.y()))
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._dragged_past_threshold and self._viewer.mode != "compare":
                self._viewer._click_at(event.position())
            self._dragging = False
            if self._viewer.mode != "compare":
                self.setCursor(Qt.CursorShape.OpenHandCursor)
        event.accept()


class _NavButton(QPushButton):
    """A round prev/next button that fades in on hover and fades out
    otherwise - floats over the canvas rather than living in a layout, so
    PageViewer positions it manually (see _position_nav_buttons)."""

    def __init__(self, text: str, parent: QWidget) -> None:
        super().__init__(text, parent)
        self.setFixedSize(42, 42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(_NAV_BUTTON_STYLE)
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(150)

    def fade_to(self, opacity: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(opacity)
        self._anim.start()


class PageViewer(QWidget):
    """Shows a single manga page. Mouse wheel zooms, left-drag pans, and
    clicking a detected text region selects it (kept in sync with the edit
    panel's list). Three modes: Original / Translated / a draggable
    before-after Compare slider."""

    region_selected = Signal(int)
    prev_requested = Signal()
    next_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._original_pixmap: QPixmap | None = None
        self._translated_pixmap: QPixmap | None = None
        self._regions: list = []
        self._selected_index: int | None = None
        self.mode = "translated"
        self._zoom = 1.0
        self._compare_fraction = 0.5
        self._reading_mode = "horizontal"  # or "vertical" - only affects which
        # edges the hover nav buttons sit on; both arrow-key pairs always work.

        self._placeholder = QLabel("Open an image, folder, or CBZ to get started")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #6d6f85; font-size: 14px;")

        self._canvas = _Canvas(self)
        self._scroll = QScrollArea()
        self._scroll.setWidget(self._canvas)
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setStyleSheet("QScrollArea { background: #141420; border: none; }")
        self._canvas.setStyleSheet("background: #141420;")

        self._btn_original = QPushButton("Original")
        self._btn_translated = QPushButton("Translated")
        self._btn_compare = QPushButton("Compare")
        for btn in (self._btn_original, self._btn_translated, self._btn_compare):
            btn.setCheckable(True)
            btn.setEnabled(False)
        self._btn_translated.setChecked(True)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_group.addButton(self._btn_original)
        self._mode_group.addButton(self._btn_translated)
        self._mode_group.addButton(self._btn_compare)
        self._btn_original.clicked.connect(lambda: self._set_mode("original"))
        self._btn_translated.clicked.connect(lambda: self._set_mode("translated"))
        self._btn_compare.clicked.connect(lambda: self._set_mode("compare"))

        self._fit_button = QPushButton("Fit")
        self._fit_button.setToolTip("Reset zoom to fit the page (Ctrl+0)")
        self._fit_button.clicked.connect(self.reset_zoom)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(14, 10, 14, 0)
        toolbar.setSpacing(6)
        toolbar.addWidget(self._btn_original)
        toolbar.addWidget(self._btn_translated)
        toolbar.addWidget(self._btn_compare)
        toolbar.addStretch()
        toolbar.addWidget(self._fit_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(toolbar)
        layout.addWidget(self._placeholder, stretch=1)
        layout.addWidget(self._scroll, stretch=1)
        self._scroll.hide()

        self._prev_button = _NavButton("‹", self)
        self._next_button = _NavButton("›", self)
        self._prev_button.clicked.connect(self.prev_requested.emit)
        self._next_button.clicked.connect(self.next_requested.emit)
        self._position_nav_buttons()

    # -- public API ---------------------------------------------------

    def set_reading_mode(self, mode: str) -> None:
        """mode: "horizontal" (nav buttons on the left/right edges) or
        "vertical" (nav buttons on the top/bottom edges). Both arrow-key
        pairs (Left/Right and Up/Down) always page through regardless of
        this setting - it only changes where the on-canvas buttons sit."""
        self._reading_mode = mode
        self._position_nav_buttons()

    def set_nav_enabled(self, has_prev: bool, has_next: bool) -> None:
        self._prev_button.setEnabled(has_prev)
        self._next_button.setEnabled(has_next)

    def set_original(self, image: np.ndarray) -> None:
        self._regions = []
        self._selected_index = None
        self._original_pixmap = _np_to_qpixmap(image)
        self._translated_pixmap = None
        self._btn_original.setEnabled(True)
        self._btn_translated.setEnabled(False)
        self._btn_compare.setEnabled(False)
        self._set_mode("original", force=True)
        # A brand new page - always fit it to the view, even though zoom/pan
        # is otherwise preserved when just switching Original/Translated/
        # Compare on the same page.
        self.reset_zoom()

    def set_translated(self, image: np.ndarray, regions: list | None = None) -> None:
        self._translated_pixmap = _np_to_qpixmap(image)
        if regions is not None:
            self._regions = regions
        self._btn_translated.setEnabled(True)
        self._btn_compare.setEnabled(True)
        self._set_mode("translated", force=True)

    def set_selected_region(self, index: int | None) -> None:
        self._selected_index = index
        self._render()

    def reset_zoom(self) -> None:
        pixmap = self._translated_pixmap or self._original_pixmap
        if pixmap is None or pixmap.width() == 0 or pixmap.height() == 0:
            return
        viewport = self._scroll.viewport().size()
        if viewport.width() > 0 and viewport.height() > 0:
            self._zoom = min(viewport.width() / pixmap.width(), viewport.height() / pixmap.height())
        else:
            self._zoom = 1.0
        self._render()
        self._scroll.horizontalScrollBar().setValue(0)
        self._scroll.verticalScrollBar().setValue(0)

    def toggle_view(self) -> None:
        """Flips between Original and Translated (from Compare, goes to
        Translated) - bound to Space in the main window."""
        if self.mode == "translated" and self._btn_original.isEnabled():
            self._set_mode("original")
        elif self._btn_translated.isEnabled():
            self._set_mode("translated")

    # -- internals ------------------------------------------------------

    def _scrollbars(self):
        return self._scroll.horizontalScrollBar(), self._scroll.verticalScrollBar()

    def _set_mode(self, mode: str, force: bool = False) -> None:
        if mode == self.mode and not force:
            return
        self.mode = mode
        {"original": self._btn_original, "translated": self._btn_translated, "compare": self._btn_compare}[
            mode
        ].setChecked(True)
        self._canvas.setCursor(Qt.CursorShape.SplitHCursor if mode == "compare" else Qt.CursorShape.OpenHandCursor)
        self._render()

    def _build_display_pixmap(self) -> QPixmap | None:
        if self.mode == "compare" and self._translated_pixmap is not None and self._original_pixmap is not None:
            width, height = self._original_pixmap.width(), self._original_pixmap.height()
            composite = QPixmap(self._original_pixmap)
            reveal_w = max(0, min(width, round(width * self._compare_fraction)))
            painter = QPainter(composite)
            painter.drawPixmap(0, 0, self._translated_pixmap, 0, 0, reveal_w, height)
            pen = QPen(QColor("#ffffff"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(reveal_w, 0, reveal_w, height)
            painter.end()
            return composite

        pixmap = self._original_pixmap if self.mode == "original" else self._translated_pixmap
        if pixmap is None:
            pixmap = self._original_pixmap
        if pixmap is None:
            return None

        # Bbox highlight only makes sense against the translated render -
        # that's the image whose regions have real translated_text to jump
        # to for editing.
        if self.mode == "translated" and self._selected_index is not None:
            if 0 <= self._selected_index < len(self._regions):
                composite = QPixmap(pixmap)
                x1, y1, x2, y2 = self._regions[self._selected_index].bbox
                painter = QPainter(composite)
                pen = QPen(QColor("#ffffff"))
                pen.setWidth(3)
                painter.setPen(pen)
                painter.setBrush(QBrush(_ACCENT_SOFT))
                painter.drawRect(x1, y1, x2 - x1, y2 - y1)
                painter.end()
                return composite
        return pixmap

    def _render(self) -> None:
        pixmap = self._build_display_pixmap()
        if pixmap is None:
            self._placeholder.show()
            self._scroll.hide()
            return

        self._placeholder.hide()
        self._scroll.show()

        scaled = pixmap.scaled(
            max(1, round(pixmap.width() * self._zoom)),
            max(1, round(pixmap.height() * self._zoom)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._canvas.setPixmap(scaled)
        self._canvas.resize(scaled.size())

    def _zoom_at(self, factor: float, label_pos: QPointF) -> None:
        pixmap = self._translated_pixmap or self._original_pixmap
        if pixmap is None:
            return
        new_zoom = max(_MIN_ZOOM, min(_MAX_ZOOM, self._zoom * factor))
        if new_zoom == self._zoom:
            return
        hbar, vbar = self._scrollbars()
        # Keep the point under the cursor stationary on screen while the
        # zoom changes, the same way QGraphicsView's AnchorUnderMouse would.
        viewport_pos = label_pos - QPointF(hbar.value(), vbar.value())
        img_pos = label_pos / self._zoom
        self._zoom = new_zoom
        self._render()
        new_label_pos = img_pos * self._zoom
        new_scroll = new_label_pos - viewport_pos
        hbar.setValue(round(new_scroll.x()))
        vbar.setValue(round(new_scroll.y()))

    def _slider_at(self, label_pos: QPointF) -> None:
        pixmap = self._original_pixmap
        if pixmap is None or self._zoom <= 0:
            return
        fraction = max(0.0, min(1.0, label_pos.x() / (pixmap.width() * self._zoom)))
        self._compare_fraction = fraction
        self._render()

    def _click_at(self, label_pos: QPointF) -> None:
        if self._zoom <= 0:
            return
        img_pos = label_pos / self._zoom
        for i, region in enumerate(self._regions):
            x1, y1, x2, y2 = region.bbox
            if x1 <= img_pos.x() <= x2 and y1 <= img_pos.y() <= y2:
                self.set_selected_region(i)
                self.region_selected.emit(i)
                return
        # A click on empty space clears the selection too - otherwise there's
        # no way to get out of a selected region once one is picked.
        self.set_selected_region(None)
        self.region_selected.emit(-1)

    def sizeHint(self):  # noqa: N802 (Qt override)
        return QSize(700, 800)

    def _position_nav_buttons(self) -> None:
        w, h = self.width(), self.height()
        bw, bh = self._prev_button.width(), self._prev_button.height()
        if self._reading_mode == "vertical":
            self._prev_button.move((w - bw) // 2, 46)
            self._next_button.move((w - bw) // 2, max(46, h - bh - 12))
        else:
            cy = max(0, (h - bh) // 2)
            self._prev_button.move(12, cy)
            self._next_button.move(max(12, w - bw - 12), cy)
        self._prev_button.raise_()
        self._next_button.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._position_nav_buttons()

    def enterEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._prev_button.fade_to(0.9)
        self._next_button.fade_to(0.9)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._prev_button.fade_to(0.0)
        self._next_button.fade_to(0.0)
        super().leaveEvent(event)
