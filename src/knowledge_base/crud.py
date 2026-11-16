from sqlalchemy.orm import Session

from src.db.models import KnowledgeEntry
from src.knowledge_base.vector_store import collection


def create_knowledge_entry(db: Session, title: str, content: str, category: str = None):
    # 1. Save to Postgres
    entry = KnowledgeEntry(title=title, content=content, category=category)
    db.add(entry)
    db.commit()
    db.refresh(entry)

    # 2. Save to ChromaDB for vector search
    collection.add(
        ids=[str(entry.id)],
        documents=[f"{title}\n{content}"],
        metadatas=[{"title": title, "category": category or "general"}],
    )

    return entry


def search_knowledge(query: str, top_k: int = 3):
    # Search ChromaDB by meaning — returns closest matches
    results = collection.query(query_texts=[query], n_results=top_k)
    return results


def list_entries(db: Session):
    return db.query(KnowledgeEntry).all()


def delete_entry(db: Session, entry_id: int):
    # Remove from both stores
    entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).first()
    if entry:
        db.delete(entry)
        db.commit()
        collection.delete(ids=[str(entry_id)])
    return entry