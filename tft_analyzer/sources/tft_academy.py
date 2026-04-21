from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from tft_analyzer.models.comp import NormalizedComp

LOGGER = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    source: str
    status: str
    message: str
    comps: list[NormalizedComp]
    started_at: str


class TftAcademyAdapter:
    """Fragile unofficial adapter for public TFT Academy pages.

    Keep all website-specific parsing here. Future source adapters can implement
    the same NormalizedComp output and feed the shared repository.
    """

    source_name = "tft_academy"

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.config.get(
                    "user_agent",
                    "TFTScreenStateAnalyzer/0.1 private-local-prototype",
                )
            }
        )

    def scrape(self) -> ScrapeResult:
        started_at = datetime.now(timezone.utc).isoformat()
        urls = self.config.get("seed_urls", [])
        if not urls:
            return ScrapeResult(self.source_name, "skipped", "No seed URLs configured", [], started_at)

        comps: list[NormalizedComp] = []
        failures: list[str] = []
        for url in urls:
            try:
                html = self._fetch(url)
                page_comps = self._parse_page(html, url)
                detail_urls = self._extract_comp_links(html, url)
                max_detail_pages = int(self.config.get("max_detail_pages", 30))
                for detail_url in detail_urls[:max_detail_pages]:
                    try:
                        detail_html = self._fetch(detail_url)
                        detail_comp = self._parse_detail_page(detail_html, detail_url)
                        if detail_comp:
                            page_comps.append(detail_comp)
                        else:
                            self._save_html_snapshot(detail_url, detail_html, "detail_no_comp")
                    except Exception as exc:
                        LOGGER.exception("TFT Academy detail scrape failed for %s", detail_url)
                        failures.append(f"{detail_url}: {exc}")
                if not page_comps:
                    self._save_html_snapshot(url, html, "no_comps")
                    failures.append(f"{url}: no comps parsed")
                comps.extend(page_comps)
            except Exception as exc:
                LOGGER.exception("TFT Academy scrape failed for %s", url)
                failures.append(f"{url}: {exc}")

        unique = self._dedupe(comps)
        status = "ok" if unique and not failures else "partial" if unique else "failed"
        message = f"Parsed {len(unique)} comps"
        if failures:
            message += "; " + " | ".join(failures[:3])
        return ScrapeResult(self.source_name, status, message, unique, started_at)

    def _fetch(self, url: str) -> str:
        timeout = float(self.config.get("request_timeout_seconds", 20))
        response = self.session.get(url, timeout=timeout)
        response.raise_for_status()
        return response.text

    def _parse_page(self, html: str, source_url: str) -> list[NormalizedComp]:
        soup = BeautifulSoup(html, "lxml")
        selectors = self.config.get("selectors", {})
        comp_selector = selectors.get("comp_card", "")
        roots = soup.select(comp_selector) if comp_selector else []
        if not roots:
            roots = self._fallback_roots(soup)

        comps: list[NormalizedComp] = []
        for root in roots:
            comp = self._parse_comp_root(root, source_url, selectors)
            if comp:
                comps.append(comp)
        return comps

    def _parse_detail_page(self, html: str, source_url: str) -> NormalizedComp | None:
        soup = BeautifulSoup(html, "lxml")
        lines = [line.strip() for line in soup.get_text("\n", strip=True).splitlines() if line.strip()]
        name = self._detail_name(lines)
        if not name:
            return None

        patch_label = self._first_match(lines, r"Patch\s+([A-Za-z0-9\.\-]+)")
        playstyle = ""
        for line in lines:
            if line.lower().startswith("playstyle"):
                playstyle = line.split(":", maxsplit=1)[-1].strip()
                break
        tier = self._detail_tier(lines, name)
        stage_notes = self._stage_notes(lines)
        alts = self._image_alts(soup)
        core_units = [self._clean_game_asset_name(alt) for alt in alts if self._looks_like_unit(alt)]
        items = [self._clean_game_asset_name(alt) for alt in alts if "item" in alt.lower()]
        augments = [self._clean_game_asset_name(alt) for alt in alts if "augment" in alt.lower()]
        tags = self._tags_from_detail(playstyle, lines)
        fields = {
            "tier": tier,
            "patch_label": patch_label,
            "playstyle": playstyle,
            "core_units": core_units,
            "carry_items": items,
            "tank_items": [],
            "augment_suggestions": augments,
            "stage_notes": stage_notes,
            "tags": tags,
        }
        confidence = self._confidence(name, fields)
        return NormalizedComp(
            name=name,
            source=self.source_name,
            source_url=source_url,
            tier=tier,
            patch_label=patch_label,
            playstyle=playstyle,
            core_units=_unique(core_units),
            optional_units=[],
            carry_items=_unique(items),
            tank_items=[],
            augment_suggestions=_unique(augments),
            stage_notes=stage_notes,
            tags=tags,
            parse_confidence=confidence,
            raw={"text_excerpt": " ".join(lines[:120])[:2000]},
        )

    def _parse_comp_root(self, root, source_url: str, selectors: dict) -> NormalizedComp | None:  # type: ignore[no-untyped-def]
        name = self._text(root, selectors.get("name")) or self._guess_name(root)
        if not name:
            return None

        href = self._href(root, selectors.get("detail_link"))
        comp_url = urljoin(source_url, href) if href else source_url
        fields = {
            "tier": self._text(root, selectors.get("tier")),
            "patch_label": self._text(root, selectors.get("patch_label")),
            "playstyle": self._text(root, selectors.get("playstyle")),
            "core_units": self._list(root, selectors.get("core_units")),
            "optional_units": self._list(root, selectors.get("optional_units")),
            "carry_items": self._list(root, selectors.get("carry_items")),
            "tank_items": self._list(root, selectors.get("tank_items")),
            "augment_suggestions": self._list(root, selectors.get("augment_suggestions")),
            "stage_notes": self._list(root, selectors.get("stage_notes")),
            "tags": self._list(root, selectors.get("tags")),
        }
        inferred = self._infer_from_text(root.get_text(" ", strip=True))
        for key, values in inferred.items():
            if key in fields and not fields[key]:
                fields[key] = values

        confidence = self._confidence(name, fields)
        return NormalizedComp(
            name=name,
            source=self.source_name,
            source_url=comp_url,
            tier=str(fields["tier"] or ""),
            patch_label=str(fields["patch_label"] or ""),
            playstyle=str(fields["playstyle"] or ""),
            core_units=list(fields["core_units"] or []),
            optional_units=list(fields["optional_units"] or []),
            carry_items=list(fields["carry_items"] or []),
            tank_items=list(fields["tank_items"] or []),
            augment_suggestions=list(fields["augment_suggestions"] or []),
            stage_notes=list(fields["stage_notes"] or []),
            tags=list(fields["tags"] or []),
            parse_confidence=confidence,
            raw={"text_excerpt": root.get_text(" ", strip=True)[:1000]},
        )

    @staticmethod
    def _load_config(path: Path) -> dict:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _fallback_roots(soup: BeautifulSoup) -> list:
        candidates = []
        for selector in ("article", "[class*=comp]", "[class*=team]", "[class*=tier]"):
            candidates.extend(soup.select(selector))
        seen: set[int] = set()
        roots = []
        for candidate in candidates:
            ident = id(candidate)
            text = candidate.get_text(" ", strip=True)
            if ident not in seen and len(text) > 20:
                seen.add(ident)
                roots.append(candidate)
        return roots[:80]

    @staticmethod
    def _extract_comp_links(html: str, source_url: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        urls: list[str] = []
        for node in soup.select("a[href]"):
            href = str(node.get("href", ""))
            if "/tierlist/comps/set-" in href:
                urls.append(urljoin(source_url, href))
        return _unique(urls)

    @staticmethod
    def _text(root, selector: str | None) -> str:  # type: ignore[no-untyped-def]
        if not selector:
            return ""
        node = root.select_one(selector)
        return node.get_text(" ", strip=True) if node else ""

    @staticmethod
    def _href(root, selector: str | None) -> str:  # type: ignore[no-untyped-def]
        if not selector:
            return ""
        node = root.select_one(selector)
        return str(node.get("href", "")) if node else ""

    @staticmethod
    def _list(root, selector: str | None) -> list[str]:  # type: ignore[no-untyped-def]
        if not selector:
            return []
        values: list[str] = []
        for node in root.select(selector):
            text = node.get("alt") or node.get("title") or node.get("aria-label") or node.get_text(" ", strip=True)
            clean = _clean_token(str(text))
            if clean:
                values.append(clean)
        return _unique(values)

    @staticmethod
    def _guess_name(root) -> str:  # type: ignore[no-untyped-def]
        for selector in ("h1", "h2", "h3", "a"):
            node = root.select_one(selector)
            if node:
                text = node.get_text(" ", strip=True)
                if 2 <= len(text) <= 80:
                    return text
        return ""

    @staticmethod
    def _infer_from_text(text: str) -> dict[str, list[str]]:
        # Best-effort fallback for pages whose CSS changed. This is intentionally
        # conservative; selectors in JSON should be preferred for real use.
        lowered = text.lower()
        inferred: dict[str, list[str]] = {}
        tag_hits = []
        for tag in ("reroll", "fast 8", "fast 9", "tempo", "vertical", "item", "economy"):
            if tag in lowered:
                tag_hits.append(tag)
        if tag_hits:
            inferred["tags"] = tag_hits
        stage_matches = re.findall(r"(stage\s+\d+[^\.;]{0,90})", text, flags=re.IGNORECASE)
        if stage_matches:
            inferred["stage_notes"] = [_clean_token(match) for match in stage_matches]
        return inferred

    @staticmethod
    def _detail_name(lines: list[str]) -> str:
        for index, line in enumerate(lines):
            if line == "Comps" and index + 1 < len(lines):
                candidate = lines[index + 1]
                if 2 <= len(candidate) <= 80 and candidate.lower() not in {"tierlist", "items", "augments"}:
                    return candidate
        for line in lines:
            if "TFT Comp Guide" in line:
                return line.replace("TFT Comp Guide", "").strip(" -")
        return ""

    @staticmethod
    def _detail_tier(lines: list[str], name: str) -> str:
        for index, line in enumerate(lines):
            if line == name and index + 1 < len(lines) and re.fullmatch(r"[SABCX]", lines[index + 1], re.IGNORECASE):
                return lines[index + 1].upper()
            if re.fullmatch(r"[SABCX]\s*tier", line, re.IGNORECASE):
                return line[0].upper()
        return ""

    @staticmethod
    def _first_match(lines: list[str], pattern: str) -> str:
        for line in lines:
            match = re.search(pattern, line, flags=re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def _stage_notes(lines: list[str]) -> list[str]:
        notes: list[str] = []
        for index, line in enumerate(lines):
            if re.fullmatch(r"Stage\s+\d+", line, flags=re.IGNORECASE):
                detail = lines[index + 1] if index + 1 < len(lines) else ""
                notes.append(_clean_token(f"{line}: {detail}"))
        return notes

    @staticmethod
    def _image_alts(soup: BeautifulSoup) -> list[str]:
        values = []
        for image in soup.select("img"):
            alt = str(image.get("alt", "")).strip()
            if alt:
                values.append(alt)
        return _unique(values)

    @staticmethod
    def _looks_like_unit(alt: str) -> bool:
        lowered = alt.lower()
        return lowered.startswith("tft") and "augment" not in lowered and "item" not in lowered and "academy logo" not in lowered

    @staticmethod
    def _clean_game_asset_name(value: str) -> str:
        clean = value
        clean = re.sub(r"^TFT\d*_", "", clean)
        clean = re.sub(r"^TFT_", "", clean)
        clean = re.sub(r"^(Character|Unit|Item|Augment)_", "", clean)
        parts = clean.split("_")
        clean = parts[-1] if len(parts) > 1 else clean
        clean = re.sub(r"(?<!^)([A-Z])", r" \1", clean).replace("  ", " ")
        return _clean_token(clean)

    @staticmethod
    def _tags_from_detail(playstyle: str, lines: list[str]) -> list[str]:
        text = " ".join([playstyle, *lines]).lower()
        tags = []
        for tag in ("fast 8", "fast 9", "reroll", "tempo", "economy", "items", "combat"):
            if tag in text:
                tags.append(tag)
        return _unique(tags)

    @staticmethod
    def _confidence(name: str, fields: dict) -> float:
        score = 0.15 if name else 0.0
        weights = {
            "tier": 0.08,
            "patch_label": 0.08,
            "playstyle": 0.08,
            "core_units": 0.18,
            "carry_items": 0.12,
            "tank_items": 0.08,
            "augment_suggestions": 0.12,
            "stage_notes": 0.06,
            "tags": 0.05,
        }
        for key, weight in weights.items():
            value = fields.get(key)
            if value:
                score += weight
        return round(min(1.0, score), 3)

    @staticmethod
    def _dedupe(comps: list[NormalizedComp]) -> list[NormalizedComp]:
        seen: set[tuple[str, str, str]] = set()
        unique: list[NormalizedComp] = []
        for comp in comps:
            key = (comp.source, comp.source_url, comp.name.lower())
            if key not in seen:
                seen.add(key)
                unique.append(comp)
        return unique

    def _save_html_snapshot(self, url: str, html: str, reason: str) -> None:
        snapshot_dir = Path(self.config.get("debug_html_dir", "debug/html_snapshots"))
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^a-zA-Z0-9]+", "_", url)[:80].strip("_")
        path = snapshot_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{reason}_{safe}.html"
        path.write_text(html, encoding="utf-8", errors="ignore")


def _clean_token(value: str) -> str:
    clean = re.sub(r"\s+", " ", value).strip(" \t\r\n:-")
    return clean[:120]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        key = value.lower()
        if key and key not in seen:
            seen.add(key)
            output.append(value)
    return output
