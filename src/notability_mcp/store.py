"""The local index: note metadata, raw bundles and searchable page text in one SQLite file."""

import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS folders (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,          -- subject, folder or divider
    parent_id TEXT
);
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    folder_id TEXT,
    created_at TEXT,             -- ISO 8601, UTC
    modified_at TEXT NOT NULL,
    page_count INTEGER,          -- NULL until the bundle is indexed
    bundle BLOB,                 -- raw NoteBundle, for rendering pages on demand
    indexed_at TEXT              -- modified_at of the bundle that was indexed
);
-- ponytail: note_id is UNINDEXED, so per-note reads scan the table; fine below ~100k pages.
CREATE VIRTUAL TABLE IF NOT EXISTS page_text USING fts5(
    title, text,
    note_id UNINDEXED, page UNINDEXED, source UNINDEXED, confidence UNINDEXED,
    tokenize = 'trigram'
);
"""


@dataclass
class Folder:
    id: str
    name: str
    kind: str
    parent_id: str | None


@dataclass
class NoteMeta:
    id: str
    title: str
    folder_id: str | None
    created_at: str | None
    modified_at: str


@dataclass
class PageText:
    page: int  # 1-based; 0 for note-level typed text
    source: str  # handwriting, typed, pdf or audio
    text: str
    confidence: float | None = None


@dataclass
class Hit:
    note_id: str
    title: str
    page: int
    source: str
    snippet: str
    score: float


def default_path() -> Path:
    if env := os.environ.get("NOTABILITY_MCP_DB"):
        return Path(env)
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "notability-mcp" / "index.db"


def connect(path: Path, *, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        uri = f"{path.resolve().as_uri()}?mode=ro"
        return sqlite3.connect(uri, uri=True, check_same_thread=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, check_same_thread=False)
    con.execute("PRAGMA journal_mode = WAL")
    con.executescript(SCHEMA)
    return con


def save_library(con: sqlite3.Connection, folders: list[Folder], notes: list[NoteMeta]) -> None:
    """Replace folder and note metadata; drop notes that no longer exist."""
    with con:
        con.execute("DELETE FROM folders")
        con.executemany(
            "INSERT INTO folders VALUES (?, ?, ?, ?)",
            [(f.id, f.name, f.kind, f.parent_id) for f in folders],
        )
        con.executemany(
            "INSERT INTO notes (id, title, folder_id, created_at, modified_at) VALUES (?,?,?,?,?)"
            " ON CONFLICT (id) DO UPDATE SET title = excluded.title,"
            " folder_id = excluded.folder_id, modified_at = excluded.modified_at",
            [(n.id, n.title, n.folder_id, n.created_at, n.modified_at) for n in notes],
        )
        con.execute(  # keep renamed titles searchable without reindexing
            "UPDATE page_text SET title = (SELECT title FROM notes WHERE id = page_text.note_id)"
            " WHERE title IS NOT (SELECT title FROM notes WHERE id = page_text.note_id)"
        )
        live = [n.id for n in notes]
        marks = ",".join("?" * len(live))
        con.execute(f"DELETE FROM notes WHERE id NOT IN ({marks})", live)
        con.execute(f"DELETE FROM page_text WHERE note_id NOT IN ({marks})", live)


def stale_notes(con: sqlite3.Connection) -> list[str]:
    """Notes whose content changed since they were last indexed, newest first."""
    rows = con.execute(
        "SELECT id FROM notes WHERE indexed_at IS NOT modified_at ORDER BY modified_at DESC"
    )
    return [r[0] for r in rows]


def save_note(
    con: sqlite3.Connection, note_id: str, bundle: bytes, page_count: int, texts: list[PageText]
) -> None:
    with con:
        (title,) = con.execute("SELECT title FROM notes WHERE id = ?", (note_id,)).fetchone()
        con.execute(
            "UPDATE notes SET bundle = ?, page_count = ?, indexed_at = modified_at WHERE id = ?",
            (bundle, page_count, note_id),
        )
        con.execute("DELETE FROM page_text WHERE note_id = ?", (note_id,))
        con.executemany(
            "INSERT INTO page_text VALUES (?, ?, ?, ?, ?, ?)",
            [(title, t.text, note_id, t.page, t.source, t.confidence) for t in texts],
        )


class QueryError(ValueError):
    pass


def fuzzy_query(text: str) -> str:
    """FTS5 query matching any 3-letter piece of any query word, for noisy OCR text."""
    words = [w for w in re.findall(r"\w+", text.lower()) if len(w) >= 3]
    if not words:
        raise QueryError("Search needs at least one word of 3 or more letters.")
    grams = dict.fromkeys(w[i : i + 3] for w in words for i in range(len(w) - 2))
    return " OR ".join(f'"{g}"' for g in grams)


def search(
    con: sqlite3.Connection, query: str, *, limit: int = 10, offset: int = 0
) -> tuple[list[Hit], bool]:
    """Best-matching pages and whether more results exist past this page."""
    rows = con.execute(
        "SELECT note_id, title, page, source,"
        " snippet(page_text, 1, '«', '»', '…', 48), bm25(page_text, 2.0, 1.0) AS score"
        " FROM page_text WHERE page_text MATCH ? ORDER BY score LIMIT ? OFFSET ?",
        (fuzzy_query(query), limit + 1, offset),
    ).fetchall()
    hits = [Hit(n, t, p, s, snip, -score) for n, t, p, s, snip, score in rows[:limit]]
    return hits, len(rows) > limit
