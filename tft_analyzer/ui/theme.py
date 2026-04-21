from __future__ import annotations

from PySide6.QtWidgets import QApplication, QWidget


APP_QSS = """
* {
    font-family: "Segoe UI", "Inter", Arial, sans-serif;
    font-size: 12px;
    color: #dbe2f4;
}
QMainWindow, QWidget#AppRoot {
    background: #080b14;
}
QWidget#Sidebar {
    background: #0b0f1d;
    border-right: 1px solid #20263a;
}
QWidget#TopBar {
    background: #101522;
    border-bottom: 1px solid #20263a;
}
QLabel#BrandTitle {
    color: #f4f7ff;
    font-size: 16px;
    font-weight: 700;
}
QLabel#PageTitle {
    color: #f4f7ff;
    font-size: 16px;
    font-weight: 700;
}
QLabel#Muted {
    color: #8992aa;
}
QLabel#SectionTitle {
    color: #f4f7ff;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0px;
}
QLabel#AccentText {
    color: #9b7cff;
    font-weight: 700;
}
QFrame#Card {
    background: #111624;
    border: 1px solid #252c42;
    border-radius: 8px;
}
QFrame#Panel {
    background: #0e1320;
    border: 1px solid #22293d;
    border-radius: 8px;
}
QFrame#StatTile {
    background: #151b2d;
    border: 1px solid #262f48;
    border-radius: 6px;
}
QPushButton {
    background: #171e31;
    border: 1px solid #303955;
    border-radius: 6px;
    color: #e7ebf7;
    min-height: 28px;
    padding: 4px 10px;
}
QPushButton:hover {
    background: #202842;
    border-color: #53618e;
}
QPushButton:pressed {
    background: #2a1f55;
    border-color: #8e6cff;
}
QPushButton#PrimaryButton {
    background: #6c4ff6;
    border-color: #8d75ff;
    color: white;
    font-weight: 700;
}
QPushButton#PrimaryButton:hover {
    background: #7d64ff;
}
QPushButton#NavButton {
    background: transparent;
    border: none;
    border-radius: 6px;
    color: #b9c1d5;
    text-align: left;
    padding: 8px 12px;
    min-height: 32px;
}
QPushButton#NavButton:hover {
    background: #171d2f;
    color: #ffffff;
}
QPushButton#NavButton:checked {
    background: #3b236f;
    color: #ffffff;
    font-weight: 700;
}
QPushButton#IconButton {
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    border-radius: 6px;
    padding: 0px;
}
QLineEdit, QComboBox, QSpinBox {
    background: #0c1120;
    border: 1px solid #27304a;
    border-radius: 6px;
    min-height: 28px;
    padding: 2px 8px;
    color: #dbe2f4;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #765dff;
}
QPlainTextEdit, QListWidget {
    background: #0c1120;
    border: 1px solid #27304a;
    border-radius: 8px;
    color: #dbe2f4;
    selection-background-color: #5131a0;
}
QListWidget::item {
    min-height: 32px;
    padding: 4px 8px;
    border-radius: 5px;
}
QListWidget::item:selected {
    background: #352260;
}
QCheckBox {
    spacing: 8px;
    color: #dbe2f4;
}
QCheckBox::indicator {
    width: 34px;
    height: 18px;
}
QCheckBox::indicator:unchecked {
    image: none;
    background: #252c42;
    border: 1px solid #39425e;
    border-radius: 9px;
}
QCheckBox::indicator:checked {
    image: none;
    background: #6c4ff6;
    border: 1px solid #8d75ff;
    border-radius: 9px;
}
QTabWidget::pane {
    border: 1px solid #252c42;
    border-radius: 8px;
    background: #111624;
}
QTabBar::tab {
    background: transparent;
    color: #9ba5bd;
    padding: 8px 14px;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected {
    color: #ffffff;
    border-bottom: 2px solid #8d75ff;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background: #0c1120;
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #303955;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


def apply_theme(target: QApplication | QWidget) -> None:
    target.setStyleSheet(APP_QSS)
