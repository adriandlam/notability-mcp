# notability-mcp

An [MCP](https://modelcontextprotocol.io) server that lets AI assistants search and read your
[Notability](https://notability.com) notes, handwriting included.

> **Unofficial.** Not affiliated with Ginger Labs. Notability has no public API; this project
> reads your own notes through the same private API the web app uses, which can change at any time.

Status: early development.

## Development

Requires [uv](https://docs.astral.sh/uv/) and macOS (handwriting OCR uses Apple's Vision framework).

```sh
make install   # create .venv and install dependencies
make hooks     # install pre-commit (ruff) and commit-msg (Conventional Commits) hooks
make check     # lint + typecheck + tests
make inspect   # open the server in MCP Inspector
```

Commits follow [Conventional Commits](https://www.conventionalcommits.org).
