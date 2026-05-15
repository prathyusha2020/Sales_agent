"""Tools exposed to Claude — the sales team copilot toolkit.

The agent is internal-facing: it helps the sales team find lead info, summarize
the pipeline, search the knowledge base, log notes, and draft follow-ups.
Each tool has a schema (sent to the API) and an executor (called when invoked).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from app import airtable_client, rag


# ─── Tool schemas (what Claude sees) ──────────────────────────────────────

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "search_leads",
        "description": (
            "Search the CRM for leads by name, email, company keyword, or note. "
            "Use this whenever the user names someone or asks 'who is...' or "
            "'find leads about...'. Returns up to 10 matches with key info."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Name, email, company, or any keyword from notes.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_lead",
        "description": (
            "Get full detail on one lead given their Airtable record ID. "
            "Returns email, products of interest, notes, deal size, when captured."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string", "description": "Airtable record ID (rec…)."}
            },
            "required": ["lead_id"],
        },
    },
    {
        "name": "list_recent_leads",
        "description": (
            "List the most recently captured leads. Use for 'who came in this week', "
            "'show me today's leads', 'latest signups'. Optionally filter by product."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "How many days back to include (default 7).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max leads to return (default 10).",
                },
                "product_name": {
                    "type": "string",
                    "description": "Optional product name to filter by (case-insensitive).",
                },
            },
        },
    },
    {
        "name": "pipeline_summary",
        "description": (
            "Aggregate pipeline numbers: total value, lead count, breakdown by "
            "product. Use for 'what's our pipeline', 'how are we doing', "
            "'breakdown by product'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "group_by": {
                    "type": "string",
                    "enum": ["product", "week"],
                    "description": "Group by 'product' or 'week' (default: product).",
                }
            },
        },
    },
    {
        "name": "search_knowledge_base",
        "description": (
            "Semantic search across product documents, testimonials, and call "
            "transcripts (RAG). Use when the user asks 'what's our pitch for X', "
            "'show me testimonials about Y', or wants to recall past customer "
            "stories. Optionally filter by context (e.g. 'Testimonial')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "context": {
                    "type": "string",
                    "description": "Optional: Testimonial, Demo, Sales Call, Client Call",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "log_note",
        "description": (
            "Append a timestamped note to a lead's record. Use when the user "
            "says 'note that I called X', 'log this for Y', 'add to her record'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string", "description": "Airtable record ID."},
                "note": {"type": "string", "description": "The note text."},
            },
            "required": ["lead_id", "note"],
        },
    },
    {
        "name": "draft_followup_email",
        "description": (
            "Draft a personalized follow-up email given a lead's name, product, "
            "and any context. Returns the draft as text — does NOT send. "
            "Always call get_lead or search_leads first to get the real info."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string"},
                "purpose": {
                    "type": "string",
                    "description": "Reason for the email: e.g. 'follow up after demo', 'check in', 'send pricing'",
                },
            },
            "required": ["lead_id", "purpose"],
        },
    },
]


# ─── Tool executor ────────────────────────────────────────────────────────

def execute_tool(name: str, args: Dict[str, Any]) -> str:
    """Run a tool by name; return a string for Claude."""
    try:
        if name == "search_leads":
            hits = airtable_client.search_leads(args["query"])[:10]
            return _format_leads(hits)

        if name == "get_lead":
            lead = airtable_client.get_lead_by_id(args["lead_id"])
            if not lead:
                return f"No lead found with id {args['lead_id']}."
            return _format_lead_detail(lead)

        if name == "list_recent_leads":
            days = int(args.get("days", 7))
            limit = int(args.get("limit", 10))
            product_name = args.get("product_name", "").lower().strip()
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            products_by_id = _products_by_id()

            recent = []
            for lead in airtable_client.list_leads():
                created = _parse_dt(lead.get("createdTime"))
                if not created or created < cutoff:
                    continue
                if product_name:
                    product_names = [
                        (products_by_id.get(pid, {}).get("Product Name") or "").lower()
                        for pid in lead.get("Products", []) or []
                    ]
                    if not any(product_name in pn for pn in product_names):
                        continue
                recent.append((created, lead))

            recent.sort(key=lambda x: x[0], reverse=True)
            return _format_leads([lead for _, lead in recent[:limit]])

        if name == "pipeline_summary":
            group_by = args.get("group_by", "product")
            products_by_id = _products_by_id()
            total_value = 0.0
            total_leads = 0
            grouped: Dict[str, Dict[str, Any]] = defaultdict(
                lambda: {"count": 0, "value": 0.0}
            )

            for lead in airtable_client.list_leads():
                total_leads += 1
                lead_value = 0.0
                lead_products: List[str] = []
                for pid in lead.get("Products", []) or []:
                    p = products_by_id.get(pid, {})
                    try:
                        lead_value += float(p.get("Price") or 0)
                    except (TypeError, ValueError):
                        pass
                    if p.get("Product Name"):
                        lead_products.append(p["Product Name"])
                total_value += lead_value

                if group_by == "product":
                    for pname in lead_products:
                        grouped[pname]["count"] += 1
                        grouped[pname]["value"] += lead_value / max(len(lead_products), 1)
                elif group_by == "week":
                    created = _parse_dt(lead.get("createdTime"))
                    if created:
                        week = created.strftime("Week of %b %d, %Y")
                        grouped[week]["count"] += 1
                        grouped[week]["value"] += lead_value

            lines = [
                f"Total pipeline: ${total_value:,.0f} across {total_leads} leads",
                "",
                f"Breakdown by {group_by}:",
            ]
            for key, info in sorted(
                grouped.items(), key=lambda kv: kv[1]["value"], reverse=True
            ):
                lines.append(
                    f"  • {key}: {info['count']} leads · ${info['value']:,.0f}"
                )
            return "\n".join(lines)

        if name == "search_knowledge_base":
            metadata_filter = {}
            if args.get("context"):
                metadata_filter["context"] = args["context"]
            hits = rag.search(args["query"], k=5, metadata_filter=metadata_filter or None)
            return _format_kb_hits(hits)

        if name == "log_note":
            airtable_client.append_lead_notes(args["lead_id"], args["note"])
            return f"Logged note on {args['lead_id']}."

        if name == "draft_followup_email":
            lead = airtable_client.get_lead_by_id(args["lead_id"])
            if not lead:
                return f"No lead found with id {args['lead_id']}."
            products_by_id = _products_by_id()
            product_names = [
                products_by_id.get(pid, {}).get("Product Name", "")
                for pid in lead.get("Products", []) or []
            ]
            return (
                "Draft this email to send (do NOT actually send — show the draft):\n\n"
                f"  Recipient: {lead.get('First Name', '')} {lead.get('Last Name', '')} "
                f"<{lead.get('Email', '')}>\n"
                f"  Products of interest: {', '.join(product_names) or 'none'}\n"
                f"  Existing notes: {lead.get('Notes', '') or 'none'}\n"
                f"  Purpose: {args['purpose']}\n\n"
                "Write a short, warm, specific draft (subject + body). "
                "Reference the products if relevant. Keep under 120 words."
            )

        return f"Unknown tool: {name}"
    except Exception as exc:
        return f"Tool '{name}' failed: {exc!s}"


# ─── Formatting helpers ───────────────────────────────────────────────────

def _products_by_id() -> Dict[str, Dict[str, Any]]:
    return {p["id"]: p for p in airtable_client.list_products()}


def _parse_dt(raw: str | None):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _format_leads(leads: List[Dict[str, Any]]) -> str:
    if not leads:
        return "No matching leads."
    products_by_id = _products_by_id()
    lines = []
    for lead in leads:
        name = (
            f"{lead.get('First Name', '')} {lead.get('Last Name', '')}".strip()
            or lead.get("Email", "(no name)")
        )
        email = lead.get("Email", "")
        product_names = [
            products_by_id.get(pid, {}).get("Product Name", "")
            for pid in lead.get("Products", []) or []
        ]
        deal_value = sum(
            float(products_by_id.get(pid, {}).get("Price") or 0)
            for pid in lead.get("Products", []) or []
        )
        lines.append(
            f"• {name} <{email}>  id={lead['id']}\n"
            f"    interested in: {', '.join(product_names) or 'nothing yet'}\n"
            f"    deal size: ${deal_value:,.0f}"
        )
    return "\n".join(lines)


def _format_lead_detail(lead: Dict[str, Any]) -> str:
    products_by_id = _products_by_id()
    product_names = [
        products_by_id.get(pid, {}).get("Product Name", "")
        for pid in lead.get("Products", []) or []
    ]
    deal_value = sum(
        float(products_by_id.get(pid, {}).get("Price") or 0)
        for pid in lead.get("Products", []) or []
    )
    name = f"{lead.get('First Name', '')} {lead.get('Last Name', '')}".strip()
    return (
        f"Lead detail (id={lead['id']}):\n"
        f"  Name: {name}\n"
        f"  Email: {lead.get('Email', '')}\n"
        f"  Captured: {lead.get('createdTime', '')}\n"
        f"  Products: {', '.join(product_names) or 'none yet'}\n"
        f"  Deal size: ${deal_value:,.0f}\n"
        f"  Notes: {lead.get('Notes', '') or '(empty)'}"
    )


def _format_kb_hits(hits: List[Dict[str, Any]]) -> str:
    if not hits:
        return "No relevant material found in the knowledge base."
    out = []
    for i, h in enumerate(hits, 1):
        meta = h.get("metadata") or {}
        out.append(
            f"[{i}] similarity={h.get('similarity', 0):.2f} "
            f"context={meta.get('context', '?')} source={meta.get('source', '?')} "
            f"url={meta.get('source_url', '')}\n"
            f"{(h.get('content') or '')[:800]}"
        )
    return "\n\n---\n\n".join(out)