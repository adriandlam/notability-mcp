# notability-mcp

An [MCP](https://modelcontextprotocol.io) server for your [Notability](https://notability.com)
notes. It lets Claude, Cursor or any other MCP client search and read what you wrote, including
handwriting.

Unofficial and not affiliated with Ginger Labs. Notability has no public API, so this reads your
notes through the private API its web app uses, which can change without notice.

## How it works

`notability-mcp sync` downloads your notes into a SQLite file on your computer and runs OCR on
every handwritten page. Search is fuzzy, so "conjugate" still finds a page the OCR read as
"conjogate". The text of PDFs your notes are written on, like lecture slides or past exams, is
searchable too.

OCR is rough, especially on math, so the server can also return any page as an image: your ink
drawn over its PDF page. A model that reads images, like Claude, can then read
your handwriting directly.

The server itself only reads that local file. It never loads your Notability token and makes no
network requests; `sync` is the only command that talks to Notability.

## Requirements

- macOS, Windows or Linux
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- A Notability account with your notes synced to it

## Setup

### 1. Log in

```sh
uvx notability-mcp login
```

You'll be asked for your `nb-auth-token`, the cookie Notability's web app signs you in with. To
copy it, sign in at [notability.com/app](https://notability.com/app), open your browser's
developer tools, go to Application (Chrome, Edge) or Storage (Firefox, Safari), then Cookies >
`https://notability.com`, and copy the value of `nb-auth-token`.

The token is saved in your system keychain: Keychain on macOS, Credential Manager on Windows,
Secret Service on Linux.

### 2. Sync

```sh
uvx notability-mcp sync
```

The first sync downloads every note and its PDFs and runs OCR on each handwritten page. For
4,000 pages that takes about 10 minutes on a Mac and up to an hour on Windows or Linux, where OCR
is slower. Later syncs only fetch notes that changed. Run it again whenever you want new notes to show up, or
schedule it with cron, launchd or Task Scheduler.

### 3. Connect your client

Most clients take this config:

```json
{
  "mcpServers": {
    "notability": {
      "command": "uvx",
      "args": ["notability-mcp", "serve"]
    }
  }
}
```

<details>
<summary>Claude Code</summary>

```sh
claude mcp add notability -s user -- uvx notability-mcp serve
```

</details>

<details>
<summary>Claude Desktop</summary>

```sh
uvx notability-mcp setup
```

This adds the server to `claude_desktop_config.json` using the full path to `uvx`, since Claude
Desktop doesn't see your shell's `PATH`. Restart Claude Desktop afterwards. To edit the file
yourself, open Settings > Developer > Edit Config.

</details>

<details>
<summary>Cursor</summary>

[Install in Cursor](https://cursor.com/en/install-mcp?name=notability&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJub3RhYmlsaXR5LW1jcCIsInNlcnZlIl19),
or add the config above to `~/.cursor/mcp.json`.

</details>

<details>
<summary>VS Code</summary>

[Install in VS Code](https://insiders.vscode.dev/redirect?url=vscode%3Amcp%2Finstall%3F%257B%2522name%2522%253A%2522notability%2522%252C%2522command%2522%253A%2522uvx%2522%252C%2522args%2522%253A%255B%2522notability-mcp%2522%252C%2522serve%2522%255D%257D),
or run:

```sh
code --add-mcp '{"name":"notability","command":"uvx","args":["notability-mcp","serve"]}'
```

</details>

<details>
<summary>Codex</summary>

```sh
codex mcp add notability -- uvx notability-mcp serve
```

</details>

Then ask something like:

- What did I write about struct allocation in CPSC 213?
- Summarize my MATH 300 notes from last week.
- Find the page where I worked out the harmonic conjugate and check my steps.

If you'd rather type `notability-mcp` than `uvx notability-mcp`, install it once with
`uv tool install notability-mcp`.

## Tools

| Tool | What it does |
|---|---|
| `notability_search_notes` | Fuzzy search over handwriting, typed text, PDF text and titles; returns pages with snippets |
| `notability_list_notes` | Lists notes by folder or recency, plus every folder and when you last synced |
| `notability_read_note` | A note's text page by page, with pages where OCR looks unreliable flagged |
| `notability_get_page_image` | One page as a PNG: your ink over the page's PDF |

All four are read-only.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `NOTABILITY_MCP_DB` | see below | Where the index is stored |
| `NOTABILITY_TOKEN` | keychain | Token for `sync`, used instead of the keychain |
| `NOTABILITY_CLIENT_VERSION` | `26.43.7` | Web app version to report, in case Notability starts rejecting old ones |

The index is stored in `~/Library/Application Support/notability-mcp` on macOS,
`%LOCALAPPDATA%\notability-mcp` on Windows and `~/.local/share/notability-mcp` on Linux.

## Limitations

- OCR is Apple's Vision framework on macOS and [RapidOCR](https://github.com/RapidAI/RapidOCR)
  elsewhere. On 20 pages of handwritten math, Vision found 44% of the key words and 7% of the
  formulas; RapidOCR found 46% and 16%. Search will usually find the right page, but read the
  page image before trusting anything exact.
- Page images show ink and PDF pages. Shapes, pasted images and typed text aren't drawn yet.
- Notes other people shared with you aren't synced.
- Audio recordings aren't transcribed or searched.
- On Linux without a keyring (a headless server, say), `login` can't save the token. Set
  `NOTABILITY_TOKEN` instead.

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
[notability-cli](https://github.com/Zpankz/notability-cli) (MIT). See
[THIRD_PARTY_NOTICES.md](https://github.com/adriandlam/notability-mcp/blob/main/THIRD_PARTY_NOTICES.md).
