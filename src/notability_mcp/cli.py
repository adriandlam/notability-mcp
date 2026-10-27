"""Command-line entry point: `notability-mcp <command>`."""

import argparse
import getpass
import logging
import os
import sys

KEYRING_SERVICE, KEYRING_USER = "notability-mcp", "nb-auth-token"
LOGIN_HELP = """\
notability-mcp reads your notes with your own Notability session token.
To copy it: sign in at https://notability.com/app, open the browser's developer tools,
then Application (Chrome) or Storage (Firefox/Safari) > Cookies > https://notability.com,
and copy the value of `nb-auth-token`. It is stored in your login Keychain.
"""


def _token() -> str | None:
    import keyring

    return os.environ.get("NOTABILITY_TOKEN") or keyring.get_password(KEYRING_SERVICE, KEYRING_USER)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="notability-mcp")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="run the MCP server on stdio")
    sub.add_parser("login", help="store your Notability session token in the Keychain")
    sub.add_parser("logout", help="remove the stored token")
    sub.add_parser("sync", help="download changed notes and update the search index")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")  # stderr; stdout is MCP's

    from notability_mcp import api

    try:
        match args.command:
            case "serve":
                from notability_mcp.server import mcp

                mcp.run()
            case "login":
                import keyring

                print(LOGIN_HELP, file=sys.stderr)
                token = getpass.getpass("nb-auth-token (input hidden): ").strip()
                library = api.fetch_library(token)
                keyring.set_password(KEYRING_SERVICE, KEYRING_USER, token)
                count = len((library.get("privateSpace") or {}).get("notes", []))
                print(f"Logged in: {count} notes. Next: notability-mcp sync", file=sys.stderr)
            case "logout":
                import keyring

                keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
                print("Token removed from the Keychain.", file=sys.stderr)
            case "sync":
                from notability_mcp import store
                from notability_mcp.sync import sync

                if not (token := _token()):
                    sys.exit("Not logged in. Run `notability-mcp login` first.")
                indexed, failed = sync(store.connect(store.default_path()), token)
                print(f"Done: {indexed} notes indexed, {failed} failed.", file=sys.stderr)
    except api.ApiError as e:
        sys.exit(str(e))
