"""Centralized config. Reads .env and exposes typed settings."""
import os
from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


# AI
ANTHROPIC_API_KEY = _required("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")

# Airtable
AIRTABLE_API_KEY = _required("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = _required("AIRTABLE_BASE_ID")
AIRTABLE_PRODUCTS_TABLE = os.getenv("AIRTABLE_PRODUCTS_TABLE", "Products")
AIRTABLE_LEADS_TABLE = os.getenv("AIRTABLE_LEADS_TABLE", "Leads")
AIRTABLE_DOCUMENTS_TABLE = os.getenv("AIRTABLE_DOCUMENTS_TABLE", "Documents")

# Supabase
SUPABASE_URL = _required("SUPABASE_URL")
SUPABASE_KEY = _required("SUPABASE_KEY")

# Embeddings (Voyage AI)
VOYAGE_API_KEY = _required("VOYAGE_API_KEY")
VOYAGE_MODEL = os.getenv("VOYAGE_MODEL", "voyage-3.5-lite")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

# Server
PORT = int(os.getenv("PORT", "3000"))
