"""Command-line entry point: `notability-mcp <command>`."""

import argparse


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="notability-mcp")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="run the MCP server on stdio")
    args = parser.parse_args(argv)

    if args.command == "serve":
        from notability_mcp.server import mcp

        mcp.run()
