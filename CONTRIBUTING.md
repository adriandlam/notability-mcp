# Contributing

Bug reports and pull requests are welcome. For anything bigger than a fix, open an issue first so
we can agree on the approach before you write it.

## Setup

You need [uv](https://docs.astral.sh/uv/getting-started/installation/).

```sh
make install   # create .venv and install dependencies
make hooks     # pre-commit (ruff) and commit-msg (Conventional Commits) hooks
make check     # lint, typecheck, tests
make inspect   # open the server in MCP Inspector
```

The tests don't need a Notability account. They run on a synthetic note bundle and ink ops
recorded by notability-cli, in `tests/fixtures`. CI runs `make check` on macOS, Windows and
Linux, because OCR differs between them: Apple's Vision framework on macOS, RapidOCR elsewhere.

To try a change on your own notes, sync into a separate index so your real one is left alone:

```sh
export NOTABILITY_MCP_DB=/tmp/notability-dev.db
uv run notability-mcp sync
make inspect
```

## Scope

The server reads the local index and nothing else. It makes no network requests and never loads
your token. Changes that write to Notability, send notes to another service or add a hosted mode
won't be merged.

## Notability's format

Notability has no public API. `api.py` talks to the endpoints its web app uses, and `bundle.py`
decodes the note bundles it downloads. Both follow
[notability-cli](https://github.com/Zpankz/notability-cli)'s reverse-engineered schema. If
Notability changes something and sync breaks, an issue with the error and the note's rough shape
(handwriting, PDF, typed text) is enough to start. Don't attach real notes.

If your change alters what gets stored for a page, bump `INDEX_VERSION` in `sync.py` so the next
sync re-indexes every note.

## Commits

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org): `feat:`,
`fix(ocr):`, `docs:` and so on. The commit-msg hook checks this.

Never put your `nb-auth-token` in an issue, a pull request or a test fixture.
