"""Connects the bot to our MCP server (src/tools/mcp_server.py) over stdio."""
import json
import sys
from typing import Any

from mcp import Client, StdioServerParameters

from src.bot.config import MCP_SERVER_PATH, PROJECT_ROOT


def open_mcp_client() -> Client:
    """Start the MCP server as a subprocess. Use as: async with open_mcp_client() as mcp:"""
    params = StdioServerParameters(
        command=sys.executable,        # same Python / venv as the bot
        args=[str(MCP_SERVER_PATH)],
        cwd=str(PROJECT_ROOT),         # so .env and ./chroma_data resolve correctly
    )
    return Client(params)


def result_text(result) -> str:
    """Join the text blocks of an MCP tool result."""
    return "".join(getattr(block, "text", "") for block in result.content)


async def call_tool_json(mcp: Client, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call one of our tools (they all return JSON strings) and parse the result."""
    result = await mcp.call_tool(name, arguments)
    text = result_text(result)
    if result.is_error:
        raise RuntimeError(f"MCP tool {name} failed: {text}")
    return json.loads(text)