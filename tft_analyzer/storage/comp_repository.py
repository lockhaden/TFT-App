from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from tft_analyzer.models.comp import NormalizedComp


class CompRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS comps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    name TEXT NOT NULL,
                    tier TEXT,
                    patch_label TEXT,
                    playstyle TEXT,
                    core_units_json TEXT NOT NULL,
                    optional_units_json TEXT NOT NULL,
                    carry_items_json TEXT NOT NULL,
                    tank_items_json TEXT NOT NULL,
                    augment_suggestions_json TEXT NOT NULL,
                    stage_notes_json TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    parse_confidence REAL NOT NULL,
                    raw_json TEXT NOT NULL,
                    scraped_at TEXT NOT NULL,
                    UNIQUE(source, source_url, name)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scrape_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    comp_count INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL
                )
                """
            )

    def upsert_comps(self, comps: list[NormalizedComp]) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            for comp in comps:
                conn.execute(
                    """
                    INSERT INTO comps (
                        source, source_url, name, tier, patch_label, playstyle,
                        core_units_json, optional_units_json, carry_items_json,
                        tank_items_json, augment_suggestions_json, stage_notes_json,
                        tags_json, parse_confidence, raw_json, scraped_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source, source_url, name) DO UPDATE SET
                        tier=excluded.tier,
                        patch_label=excluded.patch_label,
                        playstyle=excluded.playstyle,
                        core_units_json=excluded.core_units_json,
                        optional_units_json=excluded.optional_units_json,
                        carry_items_json=excluded.carry_items_json,
                        tank_items_json=excluded.tank_items_json,
                        augment_suggestions_json=excluded.augment_suggestions_json,
                        stage_notes_json=excluded.stage_notes_json,
                        tags_json=excluded.tags_json,
                        parse_confidence=excluded.parse_confidence,
                        raw_json=excluded.raw_json,
                        scraped_at=excluded.scraped_at
                    """,
                    self._row_values(comp, now),
                )
        return len(comps)

    def list_comps(self, limit: int | None = None) -> list[NormalizedComp]:
        query = "SELECT * FROM comps ORDER BY parse_confidence DESC, name ASC"
        params: tuple[int, ...] = ()
        if limit is not None:
            query += " LIMIT ?"
            params = (limit,)
        with self._connect() as conn:
            return [self._from_row(row) for row in conn.execute(query, params).fetchall()]

    def count_comps(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM comps").fetchone()
        return int(row["count"]) if row else 0

    def delete_by_source(self, source: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM comps WHERE source = ?", (source,))
        return int(cursor.rowcount or 0)

    def record_scrape_run(self, source: str, status: str, message: str, comp_count: int, started_at: str) -> None:
        finished_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO scrape_runs (source, status, message, comp_count, started_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (source, status, message, comp_count, started_at, finished_at),
            )

    def last_scrape_status(self, source: str = "tft_academy") -> dict[str, str | int]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT status, message, comp_count, finished_at
                FROM scrape_runs
                WHERE source = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (source,),
            ).fetchone()
        if not row:
            return {"status": "never", "message": "No scrape has run", "comp_count": 0, "finished_at": ""}
        return {
            "status": row["status"],
            "message": row["message"],
            "comp_count": int(row["comp_count"]),
            "finished_at": row["finished_at"],
        }

    def export_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [comp.to_dict() for comp in self.list_comps()]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _row_values(comp: NormalizedComp, scraped_at: str) -> tuple:
        return (
            comp.source,
            comp.source_url,
            comp.name,
            comp.tier,
            comp.patch_label,
            comp.playstyle,
            json.dumps(comp.core_units),
            json.dumps(comp.optional_units),
            json.dumps(comp.carry_items),
            json.dumps(comp.tank_items),
            json.dumps(comp.augment_suggestions),
            json.dumps(comp.stage_notes),
            json.dumps(comp.tags),
            comp.parse_confidence,
            json.dumps(comp.raw),
            scraped_at,
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> NormalizedComp:
        def load_list(name: str) -> list[str]:
            try:
                data = json.loads(row[name] or "[]")
            except json.JSONDecodeError:
                return []
            return [str(item) for item in data if str(item).strip()]

        try:
            raw = json.loads(row["raw_json"] or "{}")
        except json.JSONDecodeError:
            raw = {}
        return NormalizedComp(
            name=row["name"],
            source=row["source"],
            source_url=row["source_url"],
            tier=row["tier"] or "",
            patch_label=row["patch_label"] or "",
            playstyle=row["playstyle"] or "",
            core_units=load_list("core_units_json"),
            optional_units=load_list("optional_units_json"),
            carry_items=load_list("carry_items_json"),
            tank_items=load_list("tank_items_json"),
            augment_suggestions=load_list("augment_suggestions_json"),
            stage_notes=load_list("stage_notes_json"),
            tags=load_list("tags_json"),
            parse_confidence=float(row["parse_confidence"] or 0.0),
            raw=raw,
        )
