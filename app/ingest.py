"""Ingestion CLI:  python -m app.ingest

Pulls every Airtable Documents row that has Content but isn't yet Indexed,
embeds it, writes it to Supabase, then flips the Indexed checkbox.
"""
from __future__ import annotations

from app import airtable_client, rag


def _chunk(text: str, size: int = 1000, overlap: int = 150) -> list[str]:
    """Simple character-based chunking with overlap."""
    if len(text) <= size:
        return [text]
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start : start + size])
        start += size - overlap
    return chunks


def main() -> None:
    rows = airtable_client.list_documents_to_index()
    if not rows:
        print("Nothing to index. ✓")
        return

    print(f"Found {len(rows)} document(s) to index.")
    for row in rows:
        fields = row.get("fields", {})
        content = fields.get("Content", "")
        if not content:
            print(f"  - skip {row['id']} (no content)")
            continue

        # Clean any previous chunks for this document
        rag.delete_by_document_id(str(fields.get("Document ID", row["id"])))

        base_metadata = {
            "document_id": str(fields.get("Document ID", row["id"])),
            "airtable_record_id": row["id"],
            "source": fields.get("Source", ""),
            "source_url": fields.get("Source URL", ""),
            "context": fields.get("Context", ""),
            "mime_type": fields.get("Mime Type", ""),
            "description": fields.get("Description", ""),
            "system": "CRM Magic",
        }

        chunks = _chunk(content)
        for i, chunk in enumerate(chunks):
            rag.insert_document(
                content=chunk,
                metadata={**base_metadata, "chunk": i, "chunk_count": len(chunks)},
            )

        airtable_client.mark_document_indexed(row["id"])
        print(f"  ✓ {row['id']}  ({len(chunks)} chunk(s))")

    print("Done.")


if __name__ == "__main__":
    main()
