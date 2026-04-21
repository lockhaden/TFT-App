from __future__ import annotations

import logging
from pathlib import Path

from tft_analyzer.sources.tft_academy import ScrapeResult, TftAcademyAdapter
from tft_analyzer.storage.comp_repository import CompRepository

LOGGER = logging.getLogger(__name__)


class ScrapeService:
    def __init__(self, repo: CompRepository, config_path: Path) -> None:
        self.repo = repo
        self.config_path = config_path

    def refresh_tft_academy(self) -> ScrapeResult:
        adapter = TftAcademyAdapter(self.config_path)
        result = adapter.scrape()
        count = 0
        if result.comps:
            self.repo.delete_by_source(result.source)
            count = self.repo.upsert_comps(result.comps)
        self.repo.record_scrape_run(result.source, result.status, result.message, count, result.started_at)
        LOGGER.info(
            "source=%s status=%s parsed=%s message=%s",
            result.source,
            result.status,
            count,
            result.message,
        )
        return result
