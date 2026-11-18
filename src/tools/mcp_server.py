import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.resources import FileResource
from pypdf import PdfReader
from sqlalchemy import func

from src.db.config import SessionLocal
from src.db.models import Conversation, Escalation
from src.knowledge_base.crud import create_knowledge_entry, search_knowledge

# Initialize MCP server
mcp = MCPServer("slack-support-agent", version="0.1.0")


@mcp.tool()
def search_knowledge_base(query: str, top_k: int = 3) -> str:
    """Search the knowledge base for relevant docs matching a customer question."""
    results = search_knowledge(query, top_k)

    if not results["documents"][0]:
        return json.dumps({"found": False, "message": "No relevant documents found."})

    entries = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        entries.append({"content": doc, "category": meta["category"]})

    return json.dumps({"found": True, "entries": entries})


@mcp.tool()
def log_conversation(
    slack_channel_id: str,
    slack_thread_ts: str,
    slack_user_id: str,
    customer_message: str,
    bot_reply: str,
    confidence_score: float,
    was_escalated: bool = False,
) -> str:
    """Log a customer conversation (message + bot reply) to the database."""
    db = SessionLocal()
    convo = Conversation(
        slack_channel_id=slack_channel_id,
        slack_thread_ts=slack_thread_ts,
        slack_user_id=slack_user_id,
        customer_message=customer_message,
        bot_reply=bot_reply,
        confidence_score=confidence_score,
        was_escalated=was_escalated,
    )
    db.add(convo)
    db.commit()
    db.refresh(convo)
    db.close()
    return json.dumps({"logged": True, "conversation_id": convo.id})


@mcp.tool()
def escalate_to_human(conversation_id: int, reason: str) -> str:
    """Escalate a conversation to a human agent when confidence is low."""
    db = SessionLocal()
    escalation = Escalation(
        conversation_id=conversation_id,
        reason=reason,
    )
    db.add(escalation)

    convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if convo:
        convo.was_escalated = True

    db.commit()
    db.close()
    return json.dumps({"escalated": True, "conversation_id": conversation_id})


@mcp.tool()
def get_metrics() -> str:
    """Get support metrics: total conversations, escalation rate, avg confidence."""
    db = SessionLocal()

    total = db.query(func.count(Conversation.id)).scalar() or 0
    escalated = db.query(func.count(Conversation.id)).filter(Conversation.was_escalated == True).scalar() or 0
    avg_confidence = db.query(func.avg(Conversation.confidence_score)).scalar()

    db.close()
    return json.dumps({
        "total_conversations": total,
        "escalated": escalated,
        "escalation_rate": round(escalated / total * 100, 1) if total > 0 else 0,
        "avg_confidence": round(avg_confidence, 2) if avg_confidence else 0,
    })


@mcp.tool()
def add_knowledge(title: str, content: str, category: str = "general") -> str:
    """Add a new entry to the knowledge base."""
    db = SessionLocal()
    entry = create_knowledge_entry(db, title, content, category)
    db.close()
    return json.dumps({"added": True, "id": entry.id, "title": entry.title})


# ---------------------------------------------------------------------------
# Resources: read-only documents, addressed by URI
# ---------------------------------------------------------------------------

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
SALES_JOURNEY_PDF = DOCS_DIR / "mobile-new-sales-journey.pdf"

# 1) The original PDF file, served as binary (base64 "blob").
#    Useful for clients/UIs that can display or download a PDF.
mcp.add_resource(
    FileResource(
        uri="docs://mobile-new-sales-journey.pdf",
        name="mobile_new_sales_journey_pdf",
        title="Mobile New Sales Journey (PDF)",
        description="Original PDF of the SURE mobile new sales journey.",
        mime_type="application/pdf",
        path=SALES_JOURNEY_PDF,
    )
)


@lru_cache(maxsize=1)
def _sales_journey_text() -> str:
    """Extract the PDF text once and cache it (PDF parsing is slow)."""
    reader = PdfReader(SALES_JOURNEY_PDF)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(f"--- Page {i} ---\n{text}")
    return "\n\n".join(pages)


# 2) The same document as plain text, which an LLM can actually read.
@mcp.resource(
    "docs://mobile-new-sales-journey",
    title="Mobile New Sales Journey (text)",
    description="Text of the SURE mobile new sales journey: registration, island "
    "selection, bundles, cart, OMS, basket/work orders, Zendesk.",
    mime_type="text/plain",
)
def mobile_new_sales_journey() -> str:
    return _sales_journey_text()


if __name__ == "__main__":
    mcp.run()