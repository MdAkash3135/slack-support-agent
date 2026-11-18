"""Slack events: pick which messages to answer, reply in thread, log, escalate."""
import re

from slack_bolt.async_app import AsyncApp

from src.bot.agent import SupportAgent
from src.bot.config import ALLOWED_CHANNEL_IDS, CONFIDENCE_THRESHOLD, SUPPORT_TEAM_MENTION
from src.bot.mcp_client import call_tool_json

USER_MENTION = re.compile(r"<@[A-Z0-9]+>")


def register_handlers(app: AsyncApp, agent: SupportAgent) -> None:

    @app.event("message")
    async def on_message(event, context, say, logger):
        if event.get("channel") not in ALLOWED_CHANNEL_IDS:
            return
        if event.get("subtype") or event.get("bot_id"):
            return  # edits, deletes, joins, and bot messages (including our own)

        text = event.get("text", "")
        in_thread = event.get("thread_ts", event["ts"]) != event["ts"]
        bot_mentioned = f"<@{context['bot_user_id']}>" in text
        if in_thread and not bot_mentioned:
            return  # inside threads, only answer when someone @mentions the bot

        question = USER_MENTION.sub("", text).strip()
        if not question:
            return
        thread_ts = event.get("thread_ts", event["ts"])

        try:
            reply = await agent.answer(question)
        except Exception:
            logger.exception("Agent failed")
            await say(text="Sorry, something went wrong on my side. A teammate will take a look.",
                      thread_ts=thread_ts)
            return

        escalate = reply.kind != "greeting" and reply.confidence < CONFIDENCE_THRESHOLD
        message = reply.answer or "I couldn't find an answer to that."
        if escalate:
            who = f"{SUPPORT_TEAM_MENTION} " if SUPPORT_TEAM_MENTION else ""
            message += f"\n\n_{who}I'm not fully sure about this, so I've flagged it for a human teammate._"
        await say(text=message, thread_ts=thread_ts)

        # Always log; escalate when confidence is low. Done by code, not by the model.
        try:
            logged = await call_tool_json(agent.mcp, "log_conversation", {
                "slack_channel_id": event["channel"],
                "slack_thread_ts": thread_ts,
                "slack_user_id": event.get("user", ""),
                "customer_message": question,
                "bot_reply": message,
                "confidence_score": reply.confidence,
                "was_escalated": escalate,
            })
            if escalate:
                await call_tool_json(agent.mcp, "escalate_to_human", {
                    "conversation_id": logged["conversation_id"],
                    "reason": f"Low confidence ({reply.confidence:.2f})",
                })
        except Exception:
            logger.exception("Logging/escalation failed")

    @app.event("app_mention")
    async def on_mention():
        # Mentions also arrive as "message" events, which handle them above.
        # This empty handler only stops Bolt warning about an unhandled event.
        pass