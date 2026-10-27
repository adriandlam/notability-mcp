from pathlib import Path

import pytest

from notability_mcp import api, store
from notability_mcp.sync import parse_library, sync

BUNDLE = (Path(__file__).parent / "fixtures" / "synthetic_bundle.bin").read_bytes()
NOTE_ID = "6a1d9e4c-0b7f-4c1e-9a52-3f0d2b8e7c11"


def library(op_time: int) -> dict:
    """The shape of the Socket.IO `partial-update` payload (times are epoch ms)."""
    return {
        "sequenceId": 7,
        "privateSpace": {
            "folders": [{"id": "f1", "title": "Fall 2026", "parentId": None}],
            "organizers": [
                {"id": "s1", "title": "MATH 300", "parentId": "f1", "organizerType": "Subject"}
            ],
            "notes": [
                {
                    "id": NOTE_ID,
                    "title": "Lecture 1",
                    "folderId": "s1",
                    "createdAt": 1790000000000,
                    "updatedAt": 1790000000000,
                    "mostRecentOpTime": op_time,
                },
                {"id": "gone", "title": "Trashed", "updatedAt": 1, "deletedAt": 2},
            ],
        },
    }


def test_parse_library_maps_folders_and_skips_deleted_notes():
    folders, notes = parse_library(library(1790000500000))

    assert [(f.name, f.kind, f.parent_id) for f in folders] == [
        ("Fall 2026", "folder", None),
        ("MATH 300", "subject", "f1"),
    ]
    [note] = notes
    assert (note.title, note.folder_id) == ("Lecture 1", "s1")
    assert note.modified_at == "2026-09-21T14:21:40+00:00"  # the later of the two times


def test_sync_downloads_only_notes_that_changed(tmp_path, monkeypatch):
    downloads = []
    current = library(1790000500000)
    monkeypatch.setattr(api, "fetch_library", lambda token: current)
    monkeypatch.setattr(
        api, "fetch_bundle", lambda token, note_id, device: downloads.append(note_id) or BUNDLE
    )
    con = store.connect(tmp_path / "index.db")

    assert sync(con, "token") == (1, 0)
    assert sync(con, "token") == (0, 0)
    current = library(1790000900000)  # edited on another device
    assert sync(con, "token") == (1, 0)

    assert downloads == [NOTE_ID, NOTE_ID]
    [hit], _ = store.search(con, "hello")
    assert (hit.note_id, hit.source) == (NOTE_ID, "typed")


def test_bundle_ids_are_validated_before_use():
    with pytest.raises(ValueError):
        api.fetch_bundle("token", "../../graphql", "6a1d9e4c-0b7f-4c1e-9a52-3f0d2b8e7c11")
