"""MCP Server Registry — catalogue of available MCP servers for agents."""

from __future__ import annotations


# Known MCP servers that agents can use
# Format: name -> {description, install, config_template}
KNOWN_SERVERS: dict[str, dict] = {
    "web_search": {
        "name": "web_search",
        "description": "Search the web using Brave Search API",
        "package": "@anthropic-ai/mcp-server-brave-search",
        "env_vars": ["BRAVE_API_KEY"],
        "config": {
            "command": "npx",
            "args": ["-y", "@anthropic-ai/mcp-server-brave-search"],
            "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
        },
    },
    "filesystem": {
        "name": "filesystem",
        "description": "Read and write files on the local filesystem",
        "package": "@anthropic-ai/mcp-server-filesystem",
        "env_vars": [],
        "config": {
            "command": "npx",
            "args": ["-y", "@anthropic-ai/mcp-server-filesystem", "/tmp/softcat"],
        },
    },
    "fetch": {
        "name": "fetch",
        "description": "Fetch web pages and extract content",
        "package": "@anthropic-ai/mcp-server-fetch",
        "env_vars": [],
        "config": {
            "command": "npx",
            "args": ["-y", "@anthropic-ai/mcp-server-fetch"],
        },
    },
    "github": {
        "name": "github",
        "description": "Interact with GitHub repositories",
        "package": "@anthropic-ai/mcp-server-github",
        "env_vars": ["GITHUB_TOKEN"],
        "config": {
            "command": "npx",
            "args": ["-y", "@anthropic-ai/mcp-server-github"],
            "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
        },
    },
    "sqlite": {
        "name": "sqlite",
        "description": "Query SQLite databases",
        "package": "@anthropic-ai/mcp-server-sqlite",
        "env_vars": [],
        "config": {
            "command": "npx",
            "args": ["-y", "@anthropic-ai/mcp-server-sqlite"],
        },
    },
}


class MCPRegistry:
    """Registry of available MCP servers.

    Agents can use MCP servers for web search, file access,
    database queries, and other capabilities.
    """

    def __init__(self) -> None:
        self.servers = dict(KNOWN_SERVERS)

    def get(self, name: str) -> dict | None:
        """Get server info by name."""
        return self.servers.get(name)

    def list_available(self) -> list[dict]:
        """List all known MCP servers."""
        return list(self.servers.values())

    def register(self, name: str, server_info: dict) -> None:
        """Register a custom MCP server."""
        self.servers[name] = server_info
