"""OpenAI side: answer one customer question, using MCP tools."""
import json
from dataclasses import dataclass

from mcp import Client
from openai import AsyncOpenAI

from src.bot.config import MAX_TOOL_ROUNDS, OPENAI_API_KEY, OPENAI_MODEL
from src.bot.mcp_client import result_text

# The only tools the model may call itself. Logging/escalation are done by our
# code; admin tools (add_knowledge, get_metrics) stay out of customers' reach.
MODEL_TOOLS = {"search_knowledge_base"}

GREETING_REPLY = "Hi sufiur chudir vai , tumare kutta dia .... "

SYSTEM_PROMPT = """You are a customer support assistant in a Slack channel.

## Step 1: classify the message
- "greeting": the message is ONLY a greeting or small talk with no real request
  (hi, hello, hey, salam, assalamu alaikum, good morning, yo, what's up, how are you, …),
  in any language or spelling.
- "question": anything that asks for help or information, even if it starts with a greeting
  ("hi, how do refunds work?" is a question).

## Step 2: respond
- greeting: do NOT call any tool. Return {"type": "greeting"} only.
- question: always call search_knowledge_base first and answer only from what it returns.
  If it has nothing relevant, say you don't know instead of guessing.

## Style for answers
Slack formatting: short paragraphs, *bold* with single asterisks, bullets with •, no # headings.

## Output
Reply with a JSON object only, one of:
{"type": "greeting"}
{"type": "question", "answer": "<reply to the customer>", "confidence": <0 to 1>}
confidence = how sure you are the answer is correct AND supported by the knowledge base."""


@dataclass
class AgentReply:
    answer: str
    confidence: float
    kind: str = "question"  # or "greeting"


class SupportAgent:
    def __init__(self, mcp: Client):
        self.mcp = mcp
        self.openai = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.tools: list[dict] = []

    async def load_tools(self) -> None:
        """Get tool definitions from the MCP server, converted to OpenAI's format."""
        listing = await self.mcp.list_tools()
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.input_schema,
                },
            }
            for tool in listing.tools
            if tool.name in MODEL_TOOLS
        ]
        if not self.tools:
            raise RuntimeError(f"MCP server exposes none of {MODEL_TOOLS}")

    async def answer(self, question: str) -> AgentReply:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        found_anything = False

        for _ in range(MAX_TOOL_ROUNDS):
            response = await self.openai.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                tools=self.tools,
                response_format={"type": "json_object"},
            )
            msg = response.choices[0].message

            # No tool calls -> this is the final answer.
            if not msg.tool_calls:
                reply = _parse_reply(msg.content)
                if reply.kind == "greeting":
                    return reply  # no search needed, no confidence cap
                if not found_anything:
                    reply.confidence = min(reply.confidence, 0.3)  # nothing backed it up
                return reply

            # Otherwise run each requested tool and feed the results back.
            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
            })
            for tc in msg.tool_calls:
                output = await self._run_tool(tc.function.name, tc.function.arguments)
                found_anything = found_anything or _search_found(output)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": output})

        return AgentReply("Sorry, I couldn't work that one out.", 0.0)

    async def _run_tool(self, name: str, raw_args: str | None) -> str:
        if name not in MODEL_TOOLS:
            return json.dumps({"error": f"Tool {name} is not allowed"})
        try:
            result = await self.mcp.call_tool(name, json.loads(raw_args or "{}"))
            return result_text(result)
        except Exception as exc:
            return json.dumps({"error": str(exc)})


def _search_found(output: str) -> bool:
    try:
        return bool(json.loads(output).get("found"))
    except (ValueError, AttributeError):
        return False


def _parse_reply(content: str | None) -> AgentReply:
    try:
        data = json.loads(content or "")
        if data.get("type") == "greeting":
            return AgentReply(GREETING_REPLY, 1.0, kind="greeting")
        confidence = max(0.0, min(float(data.get("confidence", 0)), 1.0))
        return AgentReply(str(data.get("answer", "")).strip(), confidence)
    except (ValueError, TypeError, AttributeError):
        return AgentReply((content or "").strip(), 0.0)