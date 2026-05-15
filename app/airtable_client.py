"""Airtable wrappers for Products, Leads, and Documents tables."""
from typing import Any, Dict, List, Optional

from pyairtable import Api

from app.config import (
    AIRTABLE_API_KEY,
    AIRTABLE_BASE_ID,
    AIRTABLE_DOCUMENTS_TABLE,
    AIRTABLE_LEADS_TABLE,
    AIRTABLE_PRODUCTS_TABLE,
)

_api = Api(AIRTABLE_API_KEY)
_base = _api.base(AIRTABLE_BASE_ID)

products_table = _base.table(AIRTABLE_PRODUCTS_TABLE)
leads_table = _base.table(AIRTABLE_LEADS_TABLE)
documents_table = _base.table(AIRTABLE_DOCUMENTS_TABLE)


# ─── Products ──────────────────────────────────────────────────────────────

def list_products() -> List[Dict[str, Any]]:
    """Return all products with their key fields."""
    rows = products_table.all()
    return [
        {
            "id": r["id"],
            **{k: v for k, v in r.get("fields", {}).items()},
        }
        for r in rows
    ]


def find_product(query: str) -> List[Dict[str, Any]]:
    """Fuzzy product lookup by name or slang/abbreviations."""
    q = query.lower().strip()
    matches = []
    for p in list_products():
        haystack = " ".join(
            str(p.get(f, "")) for f in ("Product Name", "Slang", "Description")
        ).lower()
        if q in haystack:
            matches.append(p)
    return matches


# ─── Leads ─────────────────────────────────────────────────────────────────

def upsert_lead(
    email: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    product_ids: Optional[List[str]] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Create or update a lead by email."""
    existing = leads_table.all(formula=f"{{Email}} = '{email}'", max_records=1)
    fields: Dict[str, Any] = {"Email": email}
    if first_name:
        fields["First Name"] = first_name
    if last_name:
        fields["Last Name"] = last_name
    if product_ids:
        fields["Products"] = product_ids
    if notes:
        fields["Notes"] = notes

    if existing:
        return leads_table.update(existing[0]["id"], fields)
    return leads_table.create(fields)


def list_leads() -> List[Dict[str, Any]]:
    """Return every lead with its raw fields."""
    return [
        {"id": r["id"], "createdTime": r.get("createdTime"), **r.get("fields", {})}
        for r in leads_table.all()
    ]


def search_leads(query: str) -> List[Dict[str, Any]]:
    """Case-insensitive substring match across First Name, Last Name, Email, Notes."""
    q = query.lower().strip()
    if not q:
        return []
    out = []
    for lead in list_leads():
        haystack = " ".join(
            str(lead.get(f, ""))
            for f in ("First Name", "Last Name", "Email", "Notes")
        ).lower()
        if q in haystack:
            out.append(lead)
    return out


def get_lead_by_id(record_id: str) -> Optional[Dict[str, Any]]:
    """Fetch one lead with all fields."""
    try:
        r = leads_table.get(record_id)
        return {"id": r["id"], "createdTime": r.get("createdTime"), **r.get("fields", {})}
    except Exception:
        return None


def append_lead_notes(record_id: str, note: str) -> Dict[str, Any]:
    """Append a timestamped note to a lead's Notes field."""
    from datetime import datetime, timezone

    lead = leads_table.get(record_id)
    existing_notes = (lead.get("fields", {}).get("Notes") or "").strip()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    new_line = f"[{stamp}] {note}"
    combined = (existing_notes + "\n" + new_line).strip() if existing_notes else new_line
    return leads_table.update(record_id, {"Notes": combined})


# ─── Documents ─────────────────────────────────────────────────────────────

def list_documents_to_index() -> List[Dict[str, Any]]:
    """Documents that have content but aren't yet indexed."""
    formula = "AND({Content} != '', NOT({Indexed}))"
    return documents_table.all(formula=formula)


def mark_document_indexed(record_id: str) -> None:
    documents_table.update(record_id, {"Indexed": True})