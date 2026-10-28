import json

from notability_mcp import cli


def test_setup_adds_the_server_and_keeps_the_rest_of_the_config(tmp_path, monkeypatch):
    config = tmp_path / "Claude" / "claude_desktop_config.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "theme": "dark"}))
    monkeypatch.setattr(cli, "claude_desktop_config", lambda: config)
    monkeypatch.setattr(cli, "server_command", lambda: ["/bin/uvx", "notability-mcp", "serve"])
    monkeypatch.setenv("NOTABILITY_MCP_DB", str(tmp_path / "index.db"))

    cli.main(["setup"])

    assert json.loads(config.read_text()) == {
        "mcpServers": {
            "other": {"command": "x"},
            "notability": {"command": "/bin/uvx", "args": ["notability-mcp", "serve"]},
        },
        "theme": "dark",
    }
