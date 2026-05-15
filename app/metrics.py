"""Dashboard metrics — computed from Airtable on every request.

Returns numbers the dashboard renders:
  - leads_this_week, leads_last_week (for trend)
  - pipeline_value (sum of deal sizes across all leads)
  - qualified_leads (leads with at least one product attached)
  - hours_saved (estimated: 10 minutes per lead)
  - recent_activity (last 6 leads with name, company, product, value)
  - daily_leads (last 14 days, for sparkline)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from app.airtable_client import leads_table, products_table


def _parse_created(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def compute_metrics() -> Dict[str, Any]:
    """Compute all dashboard metrics in one pass."""
    products = {r["id"]: r.get("fields", {}) for r in products_table.all()}
    leads = leads_table.all()

    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    last_week_start = now - timedelta(days=14)

    leads_this_week = 0
    leads_last_week = 0
    qualified = 0
    pipeline_value = 0.0
    daily_counts: dict[str, int] = defaultdict(int)
    enriched: List[Dict[str, Any]] = []

    for r in leads:
        fields = r.get("fields", {})
        created = _parse_created(r.get("createdTime"))
        if created is None:
            continue

        product_ids = fields.get("Products") or []
        if product_ids:
            qualified += 1

        lead_value = 0.0
        product_names: list[str] = []
        for pid in product_ids:
            p = products.get(pid, {})
            try:
                lead_value += float(p.get("Price") or 0)
            except (TypeError, ValueError):
                pass
            if p.get("Product Name"):
                product_names.append(p["Product Name"])
        pipeline_value += lead_value

        if created >= week_start:
            leads_this_week += 1
        elif created >= last_week_start:
            leads_last_week += 1

        # Daily counts for the sparkline (last 14 days)
        if created >= last_week_start:
            day_key = created.strftime("%Y-%m-%d")
            daily_counts[day_key] += 1

        enriched.append(
            {
                "created": created,
                "first_name": fields.get("First Name", ""),
                "last_name": fields.get("Last Name", ""),
                "email": fields.get("Email", ""),
                "products": product_names,
                "value": lead_value,
            }
        )

    enriched.sort(key=lambda x: x["created"], reverse=True)
    recent = [
        {
            "name": (f"{e['first_name']} {e['last_name']}").strip() or e["email"],
            "email": e["email"],
            "products": e["products"],
            "value": e["value"],
            "when": _humanize(now - e["created"]),
        }
        for e in enriched[:6]
    ]

    daily_series = []
    for i in range(13, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        daily_series.append({"date": d, "count": daily_counts.get(d, 0)})

    week_change = leads_this_week - leads_last_week
    conv_rate = round((qualified / max(len(leads), 1)) * 100)

    return {
        "leads_this_week": leads_this_week,
        "leads_last_week": leads_last_week,
        "week_change": week_change,
        "total_leads": len(leads),
        "qualified_leads": qualified,
        "conversion_rate": conv_rate,
        "pipeline_value": round(pipeline_value),
        "hours_saved": round(len(leads) * 10 / 60, 1),
        "recent_activity": recent,
        "daily_series": daily_series,
    }


def _humanize(delta: timedelta) -> str:
    """Convert timedelta to '3 hours ago', 'yesterday', '4 days ago'."""
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        m = seconds // 60
        return f"{m} min ago"
    if seconds < 86400:
        h = seconds // 3600
        return f"{h} hour{'s' if h != 1 else ''} ago"
    days = seconds // 86400
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    return f"{days // 7} week{'s' if days // 7 != 1 else ''} ago"
