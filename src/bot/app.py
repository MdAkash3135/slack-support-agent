"""Entry point: uv run python -m src.bot.app"""
import asyncio
import logging

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from src.bot.agent import SupportAgent
from src.bot.config import SLACK_APP_TOKEN, SLACK_BOT_TOKEN
from src.bot.handlers import register_handlers
from src.bot.mcp_client import open_mcp_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def main() -> None:
    # One MCP connection for the bot's whole lifetime.
    async with open_mcp_client() as mcp:
        agent = SupportAgent(mcp)
        await agent.load_tools()
        logging.info("MCP ready; model tools: %s", [t["function"]["name"] for t in agent.tools])

        app = AsyncApp(token=SLACK_BOT_TOKEN)
        register_handlers(app, agent)
        await AsyncSocketModeHandler(app, SLACK_APP_TOKEN).start_async()


if __name__ == "__main__":
    asyncio.run(main())