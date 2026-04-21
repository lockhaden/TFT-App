from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Any

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QLayout,
    QLayoutItem,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from tft_analyzer.vision.crops import scaled_bbox


ACCENTS = ["#8d75ff", "#38bdf8", "#f5c84c", "#35d07f", "#ef6a8a", "#f59e0b", "#22c55e"]


def clear_layout(layout) -> None:  # type: ignore[no-untyped-def]
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            clear_layout(child_layout)


def color_for_text(text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8", errors="ignore")).digest()
    return ACCENTS[digest[0] % len(ACCENTS)]


class Card(QFrame):
    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 12, 14, 12)
        self.layout.setSpacing(10)
        if title:
            label = QLabel(title.upper())
            label.setObjectName("SectionTitle")
            self.layout.addWidget(label)


class Panel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(8)


class StatTile(QFrame):
    def __init__(self, label: str, value: Any = "?", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatTile")
        self.setMinimumHeight(58)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        self.value_label = QLabel(str(value))
        self.value_label.setStyleSheet("font-size: 20px; font-weight: 800; color: #ffffff;")
        self.label_label = QLabel(label)
        self.label_label.setObjectName("Muted")
        layout.addWidget(self.value_label)
        layout.addWidget(self.label_label)

    def set_value(self, value: Any) -> None:
        self.value_label.setText(str(value if value not in (None, "") else "?"))


class Badge(QLabel):
    def __init__(self, text: str, accent: str = "#8d75ff", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"""
            QLabel {{
                background: {accent};
                color: #080b14;
                border-radius: 5px;
                padding: 2px 7px;
                font-weight: 800;
            }}
            """
        )


class Chip(QLabel):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        display = text if len(text) <= 48 else f"{text[:45]}..."
        super().__init__(display, parent)
        self.setToolTip(text)
        self.setMinimumWidth(0)
        self.setMaximumWidth(260)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            """
            QLabel {
                background: #1a2135;
                border: 1px solid #303955;
                border-radius: 5px;
                color: #dbe2f4;
                padding: 3px 8px;
            }
            """
        )


class IconTile(QLabel):
    def __init__(self, text: str = "", active: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(34, 34)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setText(self._short(text))
        self.setToolTip(text)
        self.set_active(active, text)

    @staticmethod
    def _short(text: str) -> str:
        words = [word for word in text.replace("-", " ").split() if word]
        if not words:
            return ""
        if len(words) == 1:
            return words[0][:2].upper()
        return "".join(word[0] for word in words[:2]).upper()

    def set_active(self, active: bool, text: str = "") -> None:
        accent = color_for_text(text or self.text())
        if active:
            self.setStyleSheet(
                f"""
                QLabel {{
                    background: #141b2f;
                    border: 1px solid {accent};
                    border-radius: 5px;
                    color: #ffffff;
                    font-weight: 800;
                }}
                """
            )
        else:
            self.setStyleSheet(
                """
                QLabel {
                    background: #0b1020;
                    border: 1px solid #252c42;
                    border-radius: 5px;
                    color: #3d465f;
                }
                """
            )


class EmptyState(QFrame):
    def __init__(self, title: str, body: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        body_label = QLabel(body)
        body_label.setObjectName("Muted")
        body_label.setWordWrap(True)
        layout.addWidget(title_label)
        if body:
            layout.addWidget(body_label)
        layout.addStretch()


class SearchBar(QWidget):
    text_changed = Signal(str)

    def __init__(self, placeholder: str = "Search", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText(placeholder)
        self.search.textChanged.connect(self.text_changed)
        layout.addWidget(self.search)

    def text(self) -> str:
        return self.search.text()


class FlowLayout(QLayout):
    """Small wrapping layout used for chips/icons so long rows do not resize the app."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 6) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Orientations()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()
        effective_right = rect.right()

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > effective_right and line_height > 0:
                x = rect.x()
                y = y + line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y()


class FlowRow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.layout = FlowLayout(self)

    def set_items(self, items: Iterable[QWidget], stretch: bool = True) -> None:
        clear_layout(self.layout)
        for item in items:
            self.layout.addWidget(item)


class TileGrid(QWidget):
    def __init__(self, columns: int = 8, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.columns = columns
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(6)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

    def set_tiles(self, tiles: list[QWidget]) -> None:
        clear_layout(self.layout)
        for index, tile in enumerate(tiles):
            self.layout.addWidget(tile, index // self.columns, index % self.columns)
        self.layout.setColumnStretch(self.columns, 1)


class CalibrationPreview(QLabel):
    region_drawn = Signal(QRect)

    def __init__(self) -> None:
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(520, 300)
        self.setStyleSheet("background:#050812; color:#65708a; border: 1px solid #252c42; border-radius: 8px;")
        self.setText("Capture once to show calibration preview")
        self._start: tuple[int, int] | None = None
        self._current: QRect | None = None
        self.calibration_enabled = False
        self.show_calibration_regions = False
        self.calibration_regions: dict | None = None
        self.calibration_base_size: list[int] = [1920, 1080]
        self.calibration_image_shape: tuple[int, ...] | None = None
        self.calibration_target = ""
        self._source_pixmap: QPixmap | None = None

    def set_source_pixmap(self, pixmap: QPixmap | None, image_shape: tuple[int, ...] | None) -> None:
        self._source_pixmap = pixmap
        self.calibration_image_shape = image_shape
        self._rescale_pixmap()

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        self._rescale_pixmap()

    def _rescale_pixmap(self) -> None:
        if self._source_pixmap:
            self.setPixmap(self._source_pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.calibration_enabled and event.button() == Qt.MouseButton.LeftButton:
            self._start = (event.position().toPoint().x(), event.position().toPoint().y())
            self._current = QRect(event.position().toPoint(), event.position().toPoint())
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.calibration_enabled and self._start:
            self._current = QRect(*self._start, event.position().toPoint().x() - self._start[0], event.position().toPoint().y() - self._start[1]).normalized()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.calibration_enabled and self._current and event.button() == Qt.MouseButton.LeftButton:
            self.region_drawn.emit(self._current.normalized())
            self._start = None
            self._current = None
            self.update()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().paintEvent(event)
        if self.show_calibration_regions and self.calibration_regions and self.calibration_image_shape and self.pixmap():
            self._draw_region_boxes()
        if self._current:
            painter = QPainter(self)
            painter.setPen(QPen(Qt.GlobalColor.cyan, 2, Qt.PenStyle.DashLine))
            painter.drawRect(self._current)

    def set_calibration_context(
        self,
        regions: dict,
        base_size: list[int],
        image_shape: tuple[int, ...] | None,
        target: str,
        enabled: bool,
    ) -> None:
        self.calibration_regions = regions
        self.calibration_base_size = base_size
        self.calibration_image_shape = image_shape
        self.calibration_target = target
        self.show_calibration_regions = enabled
        self.calibration_enabled = enabled
        self.update()

    def _draw_region_boxes(self) -> None:
        pixmap = self.pixmap()
        if not pixmap or not self.calibration_image_shape or not self.calibration_regions:
            return
        pixmap_size = pixmap.size()
        offset_x = (self.width() - pixmap_size.width()) / 2
        offset_y = (self.height() - pixmap_size.height()) / 2
        image_h, image_w = self.calibration_image_shape[:2]
        sx = pixmap_size.width() / max(image_w, 1)
        sy = pixmap_size.height() / max(image_h, 1)
        painter = QPainter(self)
        selected_pen = QPen(Qt.GlobalColor.yellow, 2, Qt.PenStyle.SolidLine)
        other_pen = QPen(Qt.GlobalColor.darkCyan, 1, Qt.PenStyle.DotLine)
        for name, region in self.calibration_regions.items():
            entries = region if isinstance(region, list) else [region]
            for entry in entries:
                if not isinstance(entry, dict) or "bbox" not in entry:
                    continue
                x, y, w, h = scaled_bbox(entry["bbox"], self.calibration_base_size, self.calibration_image_shape)
                rect = QRect(
                    round(offset_x + x * sx),
                    round(offset_y + y * sy),
                    max(1, round(w * sx)),
                    max(1, round(h * sy)),
                )
                painter.setPen(selected_pen if name == self.calibration_target else other_pen)
                painter.drawRect(rect)


def add_stretch(layout) -> None:  # type: ignore[no-untyped-def]
    layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
