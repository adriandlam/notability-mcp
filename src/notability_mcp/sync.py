"""Pull the library and changed notes from Notability into the local index."""

import logging
import sqlite3
from datetime import UTC, datetime

from notability_mcp import api, store
from notability_mcp.index import index_note
from notability_mcp.store import Folder, NoteMeta

log = logging.getLogger(__name__)


def _iso(ms: float | None) -> str | None:
    return datetime.fromtimestamp(ms / 1000, UTC).isoformat(timespec="seconds") if ms else None


def parse_library(library: dict) -> tuple[list[Folder], list[NoteMeta]]:
    """Folders and live notes of the user's private space.

    ponytail: notes shared with the user (sharedNotes) are skipped; add them when needed.
    """
    space = library.get("privateSpace") or {}
    folders = [
        Folder(f["id"], f.get("title") or "Untitled", "folder", f.get("parentId"))
        for f in space.get("folders", [])
    ] + [
        Folder(
            o["id"],
            o.get("title") or "Untitled",
            (o.get("organizerType") or "").lower(),
            o.get("parentId"),
        )
        for o in space.get("organizers", [])
    ]
    notes = [
        NoteMeta(
            id=n["id"],
            title=n.get("title") or "Untitled",
            folder_id=n.get("folderId"),
            created_at=_iso(n.get("createdAt")),
            # content edits move mostRecentOpTime; updatedAt also moves on renames and moves
            modified_at=_iso(max(n.get("mostRecentOpTime") or 0, n.get("updatedAt") or 0)) or "",
        )
        for n in space.get("notes", [])
        if not n.get("deletedAt")
    ]
    return folders, notes


def sync(con: sqlite3.Connection, token: str) -> tuple[int, int]:
    """Refresh metadata, then download and index notes that changed. Returns (indexed, failed)."""
    folders, notes = parse_library(api.fetch_library(token))
    store.save_library(con, folders, notes)
    titles = {n.id: n.title for n in notes}
    stale, device = store.stale_notes(con), store.device_id(con)
    log.info("%d notes in library, %d to download and index", len(notes), len(stale))
    failed = 0
    for i, note_id in enumerate(stale, 1):
        try:
            pages = index_note(con, note_id, api.fetch_bundle(token, note_id, device))
        except api.AuthError:
            raise
        except Exception:  # one unreadable note must not stop the rest
            failed += 1
            log.exception("[%d/%d] %s: failed", i, len(stale), titles.get(note_id))
            continue
        log.info("[%d/%d] %s (%d pages)", i, len(stale), titles.get(note_id), pages)
    return len(stale) - failed, failed
