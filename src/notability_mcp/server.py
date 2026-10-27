"""The MCP server: read-only tools over the local note index."""

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver import Context, Image
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from notability_mcp import store
from notability_mcp.bundle import decode_bundle
from notability_mcp.render import MAX_EDGE, render_page

INSTRUCTIONS = """\
Read-only access to the user's Notability notes. Most notes are handwritten, so their text \
comes from OCR: it is approximate and math is often garbled.

Find notes with notability_search_notes (fuzzy, returns matching pages) or \
notability_list_notes (browse by folder or recency). Read OCR text with notability_read_note, \
and look at a page with notability_get_page_image whenever exact wording, math or diagrams \
matter. Content is as fresh as the user's last `notability-mcp sync` (see synced_at)."""

READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
READ_NOTE_MAX_CHARS = 25_000  # Claude Code warns above ~10k tokens per tool result
LOW_CONFIDENCE = 0.6


@dataclass
class App:
    path: Path
    con: sqlite3.Connection | None = None

    def db(self) -> sqlite3.Connection:
        if self.con is None:
            if not self.path.exists():
                raise ToolError(
                    f"No note index at {self.path}. Ask the user to run `notability-mcp sync`."
                )
            self.con = store.connect(self.path, readonly=True)
        return self.con


@asynccontextmanager
async def lifespan(server: MCPServer) -> AsyncIterator[App]:
    app = App(store.default_path())
    try:
        yield app
    finally:
        if app.con is not None:
            app.con.close()


mcp = MCPServer("notability", instructions=INSTRUCTIONS, lifespan=lifespan)


def _db(ctx: Context[App, Any]) -> sqlite3.Connection:
    return ctx.request_context.lifespan_context.db()


def _note(con: sqlite3.Connection, note_id: str) -> store.NoteRow:
    if note := store.get_note(con, note_id):
        return note
    raise ToolError(
        f"No note with id {note_id!r}. Find ids with notability_search_notes or "
        "notability_list_notes."
    )


def _offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    if not cursor.isdigit():
        raise ToolError("Invalid cursor. Pass next_cursor from a previous result, or omit it.")
    return int(cursor)


class SearchHit(BaseModel):
    note_id: str
    title: str
    folder: str | None
    page: int | None = Field(description="1-based page; null for typed text of the whole note")
    source: store.Source
    snippet: str = Field(description="Matching text; matched letters are marked «like this»")
    score: float


class SearchResult(BaseModel):
    hits: list[SearchHit]
    next_cursor: str | None = None
    notice: str | None = None


@mcp.tool(name="notability_search_notes", title="Search notes", annotations=READ_ONLY)
def search_notes(
    query: Annotated[
        str,
        Field(
            min_length=1,
            max_length=200,
            description="Plain words, e.g. 'harmonic conjugate'. Matching is fuzzy (3-letter "
            "pieces) to cope with OCR errors, so no quotes or operators are needed.",
        ),
    ],
    ctx: Context[App, Any],
    limit: Annotated[int, Field(ge=1, le=50)] = 10,
    cursor: Annotated[str | None, Field(description="next_cursor of a previous call")] = None,
) -> SearchResult:
    """Find note pages whose handwriting, typed text or note title match the query, best first.

    Use for a topic, term or phrase across all notes. Each hit is one page with a snippet; open
    it with notability_read_note or notability_get_page_image. To browse by folder or date,
    use notability_list_notes instead.
    """
    con, offset = _db(ctx), _offset(cursor)
    try:
        hits, more = store.search(con, query, limit=limit, offset=offset)
    except store.QueryError as e:
        raise ToolError(str(e)) from e
    folders = {n.id: n.folder for n in store.all_notes(con)}
    result = SearchResult(
        hits=[
            SearchHit(
                note_id=h.note_id,
                title=h.title,
                folder=folders.get(h.note_id),
                page=h.page or None,
                source=h.source,
                snippet=h.snippet,
                score=round(h.score, 2),
            )
            for h in hits
        ],
        next_cursor=str(offset + limit) if more else None,
    )
    if not hits:
        result.notice = (
            "No matches. Try other or fewer words, or browse with notability_list_notes; "
            "pages with only drawings or math may have little OCR text."
        )
    return result


class NoteSummary(BaseModel):
    note_id: str
    title: str
    folder: str | None
    page_count: int | None = Field(description="null until the note's content is synced")
    created_at: str | None
    modified_at: str


class NoteList(BaseModel):
    notes: list[NoteSummary]
    total: int = Field(description="Notes matching the filters, across all pages of results")
    next_cursor: str | None = None
    folders: list[str] = Field(description="Every folder path in the library")
    synced_at: str | None = Field(description="When the index was last synced (UTC)")


def _utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


@mcp.tool(name="notability_list_notes", title="List notes", annotations=READ_ONLY)
def list_notes(
    ctx: Context[App, Any],
    folder: Annotated[
        str | None,
        Field(description="Only notes whose folder path contains this text, e.g. 'MATH 300'"),
    ] = None,
    modified_after: Annotated[
        str | None, Field(description="ISO date or datetime, e.g. '2026-10-01'")
    ] = None,
    sort: Literal["recent", "title"] = "recent",
    limit: Annotated[int, Field(ge=1, le=200)] = 50,
    cursor: Annotated[str | None, Field(description="next_cursor of a previous call")] = None,
) -> NoteList:
    """List notes with folder, page count and dates, most recently modified first by default.

    Also returns every folder path. Use to browse a folder, see what changed recently, or find a
    note by title; to search inside notes use notability_search_notes.
    """
    con, offset = _db(ctx), _offset(cursor)
    notes = store.all_notes(con)
    if folder:
        notes = [n for n in notes if n.folder and folder.casefold() in n.folder.casefold()]
    if modified_after:
        try:
            since = _utc(modified_after)
        except ValueError as e:
            raise ToolError("modified_after must be an ISO date such as 2026-10-01.") from e
        notes = [n for n in notes if _utc(n.modified_at) > since]
    if sort == "title":
        notes.sort(key=lambda n: n.title.casefold())
    else:
        notes.sort(key=lambda n: n.modified_at, reverse=True)
    page = notes[offset : offset + limit]
    return NoteList(
        notes=[
            NoteSummary(
                note_id=n.id,
                title=n.title,
                folder=n.folder,
                page_count=n.page_count,
                created_at=n.created_at,
                modified_at=n.modified_at,
            )
            for n in page
        ],
        total=len(notes),
        next_cursor=str(offset + limit) if offset + limit < len(notes) else None,
        folders=sorted(set(store.folder_paths(con).values())),
        synced_at=store.synced_at(con),
    )


@mcp.tool(
    name="notability_read_note",
    title="Read note",
    annotations=READ_ONLY,
    structured_output=False,
)
def read_note(
    note_id: str,
    ctx: Context[App, Any],
    start_page: Annotated[int, Field(ge=1)] = 1,
    end_page: Annotated[int | None, Field(ge=1, description="Inclusive; default: last")] = None,
) -> str:
    """A note's text page by page, as Markdown: OCR of the handwriting plus any typed text.

    OCR is approximate; pages where it looks unreliable are flagged, so view those with
    notability_get_page_image. Output stops near 25,000 characters and says how to continue.
    """
    con = _db(ctx)
    note = _note(con, note_id)
    if note.page_count is None:
        raise ToolError("This note's content isn't synced yet. Ask the user to run sync.")
    last = min(end_page or note.page_count, note.page_count)
    if start_page > last:
        raise ToolError(f"Note has {note.page_count} pages; ask for pages 1-{note.page_count}.")

    out = [f"# {note.title}", f"{note.folder or 'No folder'} · {note.page_count} pages"]
    texts = store.note_pages(con, note_id)
    if start_page == 1 and (typed := [t.text for t in texts if t.source == "typed"]):
        out += ["", "## Typed text", *typed]
    by_page = {t.page: t for t in texts if t.source == "handwriting"}
    size = sum(len(s) for s in out)
    for number in range(start_page, last + 1):
        page = by_page.get(number)
        body = page.text if page and page.text else "(no handwriting recognized)"
        flag = ""
        if page and page.confidence is not None and page.confidence < LOW_CONFIDENCE:
            flag = " (low OCR confidence: view with notability_get_page_image)"
        section = f"\n## Page {number}{flag}\n{body}"
        if size + len(section) > READ_NOTE_MAX_CHARS and number > start_page:
            out.append(
                f"\n[Truncated: showed pages {start_page}-{number - 1} of {note.page_count}. "
                f"Continue with notability_read_note(note_id={note_id!r}, start_page={number})]"
            )
            break
        out.append(section)
        size += len(section)
    return "\n".join(out)


@mcp.tool(name="notability_get_page_image", title="View page", annotations=READ_ONLY)
def get_page_image(
    note_id: str,
    page: Annotated[int, Field(ge=1)],
    ctx: Context[App, Any],
    max_edge: Annotated[int, Field(ge=256, le=2576, description="Long edge in pixels")] = MAX_EDGE,
) -> Image:
    """One note page as a PNG, to read handwriting, math and drawings exactly as written.

    Prefer this over OCR text whenever accuracy matters. Currently draws ink only: PDF
    backgrounds, shapes and typed text are not shown.
    """
    con = _db(ctx)
    note = _note(con, note_id)
    bundle = store.note_bundle(con, note_id)
    if not bundle:
        raise ToolError("This note's content isn't synced yet. Ask the user to run sync.")
    pages = decode_bundle(bundle).pages
    if page > len(pages):
        raise ToolError(f"{note.title!r} has {len(pages)} pages; ask for 1-{len(pages)}.")
    return Image(data=render_page(pages[page - 1], max_edge), format="png")
