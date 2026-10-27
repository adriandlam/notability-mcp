# notability-mcp

An [MCP](https://modelcontextprotocol.io) server that lets AI assistants search and read your
[Notability](https://notability.com) notes, **handwriting included**.

> **Unofficial.** Not affiliated with Ginger Labs. Notability has no public API; this project
> reads your own notes through the private API its web app uses, which can change at any time.

- **Search handwriting.** Every page is OCR'd on your Mac with Apple's Vision framework, and
  search is fuzzy, so "conjugate" still finds a page the OCR read as "conjogate".
- **See the page.** Any page can be returned as an image, so the model reads your handwriting,
  math and diagrams directly instead of trusting OCR.
- **Local and private.** Notes are indexed into one SQLite file. The MCP server works offline
  from that file and never sees your Notability token; only `sync` talks to Notability.

## Tools

| Tool | What it does |
|---|---|
| `notability_search_notes` | Fuzzy search over handwriting OCR, typed text and titles; returns pages with snippets |
| `notability_list_notes` | Browse by folder or recency; also lists every folder and the last sync time |
| `notability_read_note` | A note's OCR text page by page, with unreliable pages flagged |
| `notability_get_page_image` | One page as a PNG for the model to read |

All tools are read-only.

## Setup

Requires macOS (for OCR), [uv](https://docs.astral.sh/uv/), and notes synced to your Notability
account.

1. Install:

   ```sh
   uv tool install git+https://github.com/adriandlam/notability-mcp
   ```

2. Log in. You'll be asked for your `nb-auth-token`: sign in at
   [notability.com/app](https://notability.com/app), open the browser's developer tools, go to
   Application (Chrome) or Storage (Firefox, Safari) > Cookies > `https://notability.com`, and
   copy the value of `nb-auth-token`. It is stored in your macOS login Keychain.

   ```sh
   notability-mcp login
   ```

3. Sync. The first run downloads and OCRs every note (about a quarter second per page);
   later runs only touch notes that changed. Run it again whenever you want fresh content,
   or schedule it with cron or launchd.

   ```sh
   notability-mcp sync
   ```

4. Add the server to your MCP client.

   Claude Code:

   ```sh
   claude mcp add notability -- notability-mcp serve
   ```

   Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`) or
   Cursor (`~/.cursor/mcp.json`). Desktop apps don't see your shell's `PATH`, so use the full
   path from `which notability-mcp`:

   ```json
   {
     "mcpServers": {
       "notability": {
         "command": "/Users/you/.local/bin/notability-mcp",
         "args": ["serve"]
       }
     }
   }
   ```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `NOTABILITY_MCP_DB` | `~/Library/Application Support/notability-mcp/index.db` | Index location |
| `NOTABILITY_TOKEN` | Keychain | Token for `sync`, overriding the Keychain |
| `NOTABILITY_CLIENT_VERSION` | `26.43.7` | Web client version to report, if Notability forces an update |

## Limitations

- OCR handles prose reasonably and math poorly. Search finds the page; read the page image for
  anything exact.
- Page images show ink only. PDF backgrounds, shapes and typed text are not drawn yet.
- Notes shared with you by others are not synced yet.

## Development

```sh
make install   # create .venv and install dependencies
make hooks     # pre-commit (ruff) and commit-msg (Conventional Commits) hooks
make check     # lint, typecheck, tests
make inspect   # open the server in MCP Inspector
```

Commits follow [Conventional Commits](https://www.conventionalcommits.org).

## Credits

The Notability wire format was reverse-engineered by
[notability-cli](https://github.com/Zpankz/notability-cli) (MIT); see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
