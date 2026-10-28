import json
import sys

from notability_mcp import cli


def test_setup_adds_the_server_and_keeps_the_rest_of_the_config(tmp_path, monkeypatch):
    config = tmp_path / "Claude" / "claude_desktop_config.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "theme": "dark"}))
    config.chmod(0o600)  # it can hold other servers' API keys
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
    if sys.platform != "win32":  # Windows has no Unix permission bits
        assert config.stat().st_mode & 0o777 == 0o600
