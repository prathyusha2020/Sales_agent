"""Voyage AI embeddings — fast, lightweight, free tier.

Uses voyage-3.5-lite (1024 dims) by default. Get a key at https://voyageai.com/.
Input type matters: pass 'document' when indexing and 'query' when searching —
Voyage models are trained asymmetrically and this measurably improves recall.
"""
from typing import List

import voyageai

from app.config import VOYAGE_API_KEY, VOYAGE_MODEL

_client = voyageai.Client(api_key=VOYAGE_API_KEY)


def embed_text(text: str, input_type: str = "query") -> List[float]:
    """Return one embedding. `input_type` should be 'query' or 'document'."""
    result = _client.embed([text], model=VOYAGE_MODEL, input_type=input_type)
    return result.embeddings[0]


def embed_batch(texts: List[str], input_type: str = "document") -> List[List[float]]:
    """Batch-embed. Voyage caps each batch at 1000 items / model token budget,
    so we chunk defensively for safety on large ingests."""
    out: List[List[float]] = []
    BATCH = 128
    for i in range(0, len(texts), BATCH):
        slice_ = texts[i : i + BATCH]
        result = _client.embed(slice_, model=VOYAGE_MODEL, input_type=input_type)
        out.extend(result.embeddings)
    return out
