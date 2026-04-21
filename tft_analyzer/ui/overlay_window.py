from __future__ import annotations

import ctypes
import logging

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from tft_analyzer.models.comp import CompCandidate
from tft_analyzer.models.game_state import GameState

LOGGER = logging.getLogger(__name__)


class OverlayWindow(QWidget):
    """Passive desktop overlay.

    This is an ordinary transparent always-on-top companion window. It does not
    inject into the game, hook DirectX, read memory, or control input.
    """

    def __init__(self) -> None:
        super().__init__()
        self._drag_start: QPoint | None = None
        self.setWindowTitle("TFT Analyzer Overlay")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowOpacity(0.88)
        self.resize(360, 260)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        self.title = QLabel("TFT Screen State - drag to move")
        self.summary = QLabel("Waiting for capture...")
        self.candidates = QLabel("")
        for label in (self.title, self.summary, self.candidates):
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        layout.addWidget(self.title)
        layout.addWidget(self.summary)
        layout.addWidget(self.candidates)
        layout.addStretch()
        self.setStyleSheet(
            """
            QWidget {
                background-color: rgba(12, 16, 20, 210);
                border: 1px solid rgba(160, 180, 190, 120);
                border-radius: 8px;
            }
            QLabel {
                color: #f2f6f8;
                background: transparent;
                border: none;
                font-size: 12px;
            }
            QLabel:first-child {
                font-size: 14px;
                font-weight: 700;
            }
            """
        )

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().showEvent(event)
        self._exclude_from_capture()

    def _exclude_from_capture(self) -> None:
        """Ask Windows not to include this passive overlay in screen captures.

        This Windows-only hint can fail on older builds, remote sessions, or some
        driver paths. The app still works if it fails; captures may simply include
        the overlay in those environments.
        """
        try:
            hwnd = int(self.winId())
            wda_excludefromcapture = 0x00000011
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, wda_excludefromcapture)
        except Exception:
            LOGGER.debug("Could not exclude overlay from capture", exc_info=True)

    def update_state(self, state: GameState | None, candidates: list[CompCandidate]) -> None:
        if state is None:
            self.summary.setText("Waiting for capture...")
            self.candidates.setText("")
            return

        stage = state.stage.value if state.stage.known else "?"
        hp = state.hp.value if state.hp.known else "?"
        gold = state.gold.value if state.gold.known else "?"
        level = state.level.value if state.level.known else "?"
        board = sum(1 for slot in state.board_slots if slot.occupied)
        bench = sum(1 for slot in state.bench_slots if slot.occupied)
        items = sum(1 for slot in state.item_slots if slot.occupied)
        warnings = len(state.warnings) + sum(
            1
            for field in (state.stage, state.hp, state.gold, state.level)
            if not field.known or field.confidence < 0.45
        )

        self.summary.setText(
            "\n".join(
                [
                    f"Stage {stage} | HP {hp} | Gold {gold} | Level {level}",
                    f"Champs on board: {board} | Bench {bench}/{len(state.bench_slots)} | Items {items}/{len(state.item_slots)}",
                    f"Warnings: {warnings}",
                ]
            )
        )
        if not candidates:
            self.candidates.setText("Cached comp fits: none available")
            return
        lines = ["Cached comp fits:"]
        for candidate in candidates[:3]:
            lines.append(f"- {candidate.name}: {candidate.score:.1f} ({candidate.confidence:.2f})")
        self.candidates.setText("\n".join(lines))

    def set_click_through(self, enabled: bool) -> None:
        flags = self.windowFlags()
        if enabled:
            flags |= Qt.WindowType.WindowTransparentForInput
        else:
            flags &= ~Qt.WindowType.WindowTransparentForInput
        visible = self.isVisible()
        self.setWindowFlags(flags)
        if visible:
            self.show()
            self._exclude_from_capture()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_start)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_start = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        event.accept()
