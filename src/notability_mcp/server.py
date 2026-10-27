"""The MCP server: read-only tools over the local note index."""

from mcp.server import MCPServer

mcp = MCPServer(
    "notability",
    instructions="Read-only access to the user's Notability notes.",
)
