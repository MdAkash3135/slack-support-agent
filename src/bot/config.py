"""Bot settings, loaded once from the project's .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is missing from .env")
    return value


SLACK_BOT_TOKEN = _require("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = _require("SLACK_APP_TOKEN")
OPENAI_API_KEY = _require("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL") or "gpt-5-mini"

# The bot only answers in these channels; every other channel is ignored.
ALLOWED_CHANNEL_IDS = frozenset(
    c.strip() for c in _require("ALLOWED_CHANNEL_IDS").split(",") if c.strip()
)

# Below this confidence the bot escalates to a human.
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD") or 0.6)

# Optional: who to tag on escalation, e.g. <@U0123ABCD> or <!subteam^S0123ABCD>
SUPPORT_TEAM_MENTION = os.getenv("SUPPORT_TEAM_MENTION", "").strip()

MAX_TOOL_ROUNDS = 5
MCP_SERVER_PATH = PROJECT_ROOT / "src" / "tools" / "mcp_server.py"

print(f"Loaded bot config from {PROJECT_ROOT / '.env'}")