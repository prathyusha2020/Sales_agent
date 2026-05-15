"""Supabase vector store for RAG. Insert + similarity search."""
from typing import Any, Dict, List, Optional

from supabase import Client, create_client

from app.config import SUPABASE_KEY, SUPABASE_URL
from app.embeddings import embed_text


def _client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def insert_document(content: str, metadata: Dict[str, Any]) -> None:
    """Embed `content` and insert one row into the documents table."""
    embedding = embed_text(content, input_type="document")
    _client().table("documents").insert(
        {"content": content, "metadata": metadata, "embedding": embedding}
    ).execute()


def search(
    query: str, k: int = 5, metadata_filter: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Semantic search. `metadata_filter` is a JSONB containment filter,
    e.g. {"context": "testimonial"} returns only testimonials.
    """
    embedding = embed_text(query, input_type="query")
    resp = (
        _client()
        .rpc(
            "match_documents",
            {
                "query_embedding": embedding,
                "match_count": k,
                "filter": metadata_filter or {},
            },
        )
        .execute()
    )
    return resp.data or []


def delete_by_document_id(document_id: str) -> None:
    """Remove all chunks belonging to one Airtable document (for re-index)."""
    _client().table("documents").delete().filter(
        "metadata->>document_id", "eq", document_id
    ).execute()
