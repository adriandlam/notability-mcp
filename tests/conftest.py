import json
from pathlib import Path

import pytest

from notability_mcp.bundle import Note, build_note, read_ops

FIXTURES = Path(__file__).parent / "fixtures"


def event_ops(name: str):
    """Ops from a server-acknowledged AppendOpsEvent captured by notability-cli."""
    fixture = json.loads((FIXTURES / f"{name}.json").read_text())
    return read_ops(bytes.fromhex(fixture["append_ops_event_hex"]), ops_field=0)


@pytest.fixture
def ink_note() -> Note:
    """One pen stroke at (80, 300) on the implicit first page, streamed in two chunks."""
    return build_note("ink-note", event_ops("25_ink_pen") + event_ops("26_ink_add_path"))
