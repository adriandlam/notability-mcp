import pytest

from notability_mcp import store
from notability_mcp.store import Folder, NoteMeta, PageText

MATH = NoteMeta("n1", "Complex Analysis", "math", None, "2026-10-01T00:00:00Z")
FOOD = NoteMeta("n2", "Groceries", None, None, "2026-10-02T00:00:00Z")


@pytest.fixture
def con(tmp_path):
    con = store.connect(tmp_path / "index.db")
    store.save_library(con, [Folder("math", "MATH 300", "subject", None)], [MATH, FOOD])
    return con


def index(con, note_id, *texts):
    pages = [PageText(i + 1, "handwriting", t) for i, t in enumerate(texts)]
    store.save_note(con, note_id, b"bundle", len(pages), pages)


def test_fuzzy_search_tolerates_ocr_misspellings(con):
    # real Apple Vision output for "v harmonic conjugate of u in D"
    index(con, "n1", "Cauchy-Riemann equations", "V homeria conjogate ot u in D")
    index(con, "n2", "eggs, milk, bread")

    hits, more = store.search(con, "harmonic conjugate")

    assert [(h.note_id, h.page) for h in hits] == [("n1", 2)]
    assert "«" in hits[0].snippet
    assert not more


def test_titles_are_searchable_and_follow_renames(con):
    index(con, "n2", "")
    store.save_library(
        con, [], [MATH, NoteMeta("n2", "Shopping list", None, None, FOOD.modified_at)]
    )

    [hit], _ = store.search(con, "shopping")

    assert (hit.note_id, hit.title) == ("n2", "Shopping list")


def test_modified_notes_go_stale(con):
    assert set(store.stale_notes(con)) == {"n1", "n2"}
    index(con, "n1", "page one")
    assert store.stale_notes(con) == ["n2"]

    store.save_library(con, [], [NoteMeta("n1", MATH.title, None, None, "2026-10-09T00:00:00Z")])

    assert store.stale_notes(con) == ["n1"]


def test_deleted_notes_leave_the_index(con):
    index(con, "n2", "eggs, milk, bread")

    store.save_library(con, [], [MATH])

    assert store.search(con, "bread") == ([], False)


def test_query_needs_a_real_word(con):
    with pytest.raises(store.QueryError):
        store.search(con, "is a")
