"""python -m src.bot.smoke_test               -> tests MCP only
   python -m src.bot.smoke_test "a question"  -> also tests the OpenAI agent"""
import asyncio
import sys

from src.bot.mcp_client import call_tool_json, open_mcp_client


async def main() -> None:
    async with open_mcp_client() as mcp:
        tools = await mcp.list_tools()
        print("Tools:", [t.name for t in tools.tools])
        print("Search:", await call_tool_json(mcp, "search_knowledge_base", {"query": "registration", "top_k": 1}))
        print("Metrics:", await call_tool_json(mcp, "get_metrics", {}))

        if len(sys.argv) > 1:
            from src.bot.agent import SupportAgent

            agent = SupportAgent(mcp)
            await agent.load_tools()
            reply = await agent.answer(" ".join(sys.argv[1:]))
            print(f"\nConfidence: {reply.confidence:.2f}\n{reply.answer}")


asyncio.run(main())