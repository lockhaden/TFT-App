from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import cv2
import numpy as np

LOGGER = logging.getLogger(__name__)


@dataclass
class OcrResult:
    text: str
    confidence: float


class OcrEngine:
    def __init__(self, tesseract_cmd: str = "", language: str = "eng") -> None:
        self.language = language
        self.available = False
        try:
            import pytesseract

            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            pytesseract.get_tesseract_version()
            self._pytesseract = pytesseract
            self.available = True
        except Exception:
            LOGGER.warning("Tesseract OCR is unavailable; OCR fields will be unknown")
            self._pytesseract = None

    def read_text(self, image_bgr: np.ndarray, whitelist: str | None = None) -> OcrResult:
        if not self.available or self._pytesseract is None:
            return OcrResult("", 0.0)
        configs = ["--psm 7", "--psm 8", "--psm 13"] if whitelist else ["--psm 6", "--psm 7"]
        if whitelist:
            configs = [f"{config} -c tessedit_char_whitelist={whitelist}" for config in configs]
        best = OcrResult("", 0.0)
        for prepared in self._prepare_variants(image_bgr):
            for config in configs:
                result = self._read_prepared(prepared, config)
                if result.text and result.confidence >= best.confidence:
                    best = result
        return best

    def _read_prepared(self, prepared: np.ndarray, config: str) -> OcrResult:
        try:
            data = self._pytesseract.image_to_data(
                prepared,
                lang=self.language,
                config=config,
                output_type=self._pytesseract.Output.DICT,
            )
        except Exception:
            LOGGER.exception("OCR failed")
            return OcrResult("", 0.0)

        words: list[str] = []
        confidences: list[float] = []
        for text, conf in zip(data.get("text", []), data.get("conf", []), strict=False):
            clean = str(text).strip()
            try:
                score = float(conf)
            except ValueError:
                score = -1.0
            if clean:
                words.append(clean)
            if score >= 0:
                confidences.append(score / 100.0)
        return OcrResult(" ".join(words), sum(confidences) / len(confidences) if confidences else 0.0)

    @staticmethod
    def _prepare_variants(image_bgr: np.ndarray) -> list[np.ndarray]:
        if image_bgr.size == 0:
            return []
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC)
        sharp = cv2.addWeighted(gray, 1.8, cv2.GaussianBlur(gray, (0, 0), 1.2), -0.8, 0)
        blur = cv2.GaussianBlur(sharp, (3, 3), 0)
        _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        _, inv_otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        adaptive = cv2.adaptiveThreshold(
            blur,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            7,
        )
        return [sharp, otsu, inv_otsu, adaptive]


def parse_int(result: OcrResult, min_value: int = 0, max_value: int = 999, min_confidence: float = 0.12) -> tuple[int | None, float]:
    if result.confidence < min_confidence:
        return None, result.confidence
    match = re.search(r"\d+", result.text.replace("O", "0"))
    if not match:
        return None, 0.0
    value = int(match.group(0))
    if min_value <= value <= max_value:
        return value, result.confidence
    return None, result.confidence * 0.4


def parse_stage(result: OcrResult) -> tuple[str | None, float]:
    match = re.search(r"(\d+)\s*[-:]\s*(\d+)", result.text)
    if match:
        return f"{match.group(1)}-{match.group(2)}", result.confidence
    return None, result.confidence * 0.5
