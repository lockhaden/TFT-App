from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from tft_analyzer.config.config_manager import ConfigManager
from tft_analyzer.ui.main_window import MainWindow


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def configure_logging() -> None:
    Path("debug").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("debug/tft_screen_state_analyzer.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main() -> int:
    os.chdir(app_root())
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("TFT Screen State Analyzer")

    config = ConfigManager(Path("config/default_config.json"))
    window = MainWindow(config)
    window.resize(1280, 820)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
