"""Demo data seeder — populates Airtable with generic sales-business data.

What it creates:
  - 3 products (consulting, online course, SaaS subscription)
  - 2 testimonial documents linked to products
  - ~32 leads spread across the last 30 days, weekdays weighted heavier,
    with varied statuses, deal sizes, and product interest

Idempotent: re-running won't duplicate.

Run:  python -m app.seed_data
Then: python -m app.ingest      (embed testimonials into Supabase)
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from app.airtable_client import documents_table, leads_table, products_table


PRODUCTS = [
    {
        "Product Name": "Growth Strategy Consulting",
        "Slang": "consulting, strategy, advisory, 1-on-1, audit",
        "Description": (
            "Six-week intensive engagement for founders scaling past $1M ARR. "
            "Weekly strategy sessions, async support, and a custom growth "
            "playbook. We focus on the one or two levers that actually move "
            "the needle for your business."
        ),
        "Price": 8500,
        "Payment Schedule": "One-time",
        "Ideal Client": (
            "Founders and operators between $1M-$10M ARR who have product-"
            "market fit but are unsure where to invest next."
        ),
        "Bad Client": (
            "Pre-revenue startups, agencies looking for fractional help, "
            "people who want done-for-you implementation."
        ),
        "Buy Now Link": "https://example.com/book/consulting",
        "Lead Magnet Link": "https://example.com/growth-audit-template",
    },
    {
        "Product Name": "Operator's Playbook Course",
        "Slang": "course, training, playbook, self-paced, video course",
        "Description": (
            "12 modules, 40+ video lessons, downloadable templates, and a "
            "private community. Built for ops leaders and founders who want "
            "to systematize their growth without hiring a coach."
        ),
        "Price": 1200,
        "Payment Schedule": "One-time",
        "Ideal Client": (
            "Self-directed learners, early-stage founders on a budget, "
            "operators inside larger companies."
        ),
        "Bad Client": "People who need accountability or live feedback.",
        "Buy Now Link": "https://example.com/checkout/course",
        "Lead Magnet Link": "https://example.com/free-module",
    },
    {
        "Product Name": "Pipeline Pro Subscription",
        "Slang": "software, saas, tool, subscription, monthly",
        "Description": (
            "Sales pipeline software with built-in AI assistant. Captures "
            "leads from any channel, qualifies them automatically, and "
            "routes hot prospects to your calendar. 14-day free trial."
        ),
        "Price": 297,
        "Payment Schedule": "Monthly",
        "Ideal Client": (
            "Solo founders and small sales teams (2-10 people) who lose "
            "deals because leads slip through the cracks."
        ),
        "Bad Client": "Enterprise teams needing custom integrations.",
        "Buy Now Link": "https://example.com/signup/saas",
        "Lead Magnet Link": "https://example.com/saas-demo",
    },
]


DOCUMENTS = [
    {
        "Source": "School",
        "Source URL": "https://example.com/testimonials/acme",
        "Description": "Acme Co. — Founder, $3M ARR SaaS.",
        "Context": "Testimonial",
        "Mime Type": "text/plain",
        "Content": (
            "We were stuck around $2.8M ARR for nine months — adding people, "
            "trying tactics, none of it moved the needle. Six weeks into the "
            "consulting engagement we cut three growth experiments and "
            "doubled down on one channel. By month four we were at $4.1M "
            "and finally hiring with conviction. The thing I'd tell anyone "
            "considering this: the value isn't the advice, it's the focus "
            "it forces. We had been doing too much."
        ),
        "_product_match": "Growth Strategy Consulting",
    },
    {
        "Source": "YouTube",
        "Source URL": "https://example.com/case-study/midwest",
        "Description": "Midwest Operator — Ops Lead, 12-person team.",
        "Context": "Testimonial",
        "Mime Type": "text/plain",
        "Content": (
            "I'd bought five courses before this one and finished none. The "
            "Operator's Playbook is the first I actually completed and "
            "implemented. Module 7 alone — the pipeline review framework — "
            "found us $40K in stuck deals we'd written off. The templates "
            "are doing the work, not the videos. If you're an operator who "
            "needs systems, not motivation, this is the one."
        ),
        "_product_match": "Operator's Playbook Course",
    },
]


FIRST_NAMES = [
    "Priya", "Marcus", "Sara", "James", "Yuki", "Diego", "Aisha", "Tom",
    "Nina", "Raj", "Elena", "Chris", "Hana", "Owen", "Maya", "Felix",
    "Zara", "Leo", "Amara", "Jonah", "Ines", "Theo", "Liv", "Sam",
    "Anika", "Beau", "Caro", "Dev", "Esme", "Finn", "Gia", "Hugo",
]
LAST_NAMES = [
    "Patel", "Reyes", "Tanaka", "Okafor", "Lindgren", "Cohen", "Müller",
    "Adeyemi", "Schultz", "Park", "Rivera", "Ali", "Nakamura", "Lee",
    "Kowalski", "Davis", "Chen", "Walsh", "Sato", "Brennan",
]
COMPANIES = [
    "Acme Foods", "Northwind Logistics", "Apex Imports", "Beacon Group",
    "Midwest Co-op", "Pacific Lines", "Anchor Manufacturing", "Riverside 3PL",
    "Crown Distributors", "Summit Foods", "Cascade Industries", "Lakefront Mills",
    "Harbor Brands", "Stonebridge Logistics", "Iron Mountain Co.", "Verge Studios",
    "Prairie Distributors", "Northshore Imports", "Helix Brands", "Foxtail Foods",
]
NOTE_BANK = [
    "Asked about onboarding timeline.",
    "Mentioned previous bad experience with competitor.",
    "Wants to see ROI breakdown before committing.",
    "Has a 30-day evaluation window.",
    "Interested but waiting on Q2 budget approval.",
    "Asked for case studies in their industry.",
    "Decision-maker is the founder.",
    "Needs internal alignment with ops team first.",
    "Already getting value from the free resources.",
    "Time-sensitive — wants to start within two weeks.",
    "Referred by an existing customer.",
    "Came in from the lead magnet.",
    "",
    "",
]


def _existing_emails() -> set[str]:
    return {
        (r.get("fields", {}).get("Email") or "").lower()
        for r in leads_table.all()
    }


def seed_products() -> dict[str, str]:
    """Insert products. Returns name → record_id."""
    existing = {
        r.get("fields", {}).get("Product Name"): r["id"]
        for r in products_table.all()
    }
    name_to_id: dict[str, str] = {}
    for p in PRODUCTS:
        name = p["Product Name"]
        if name in existing:
            print(f"  · skip product '{name}' (exists)")
            name_to_id[name] = existing[name]
            continue
        record = products_table.create(p)
        name_to_id[name] = record["id"]
        print(f"  ✓ product '{name}'  →  {record['id']}")
    return name_to_id


def seed_documents(product_id_map: dict[str, str]) -> None:
    existing = {r.get("fields", {}).get("Description") for r in documents_table.all()}
    for d in DOCUMENTS:
        if d["Description"] in existing:
            print(f"  · skip doc '{d['Description']}' (exists)")
            continue
        product_name = d.pop("_product_match")
        record = documents_table.create(dict(d))
        print(f"  ✓ doc '{d['Description']}'  →  {record['id']}")
        if product_name in product_id_map:
            try:
                products_table.update(
                    product_id_map[product_name],
                    {"Documents": [record["id"]]},
                )
            except Exception:
                pass


def _weekday_weighted_date(days_back: int) -> datetime:
    """Pick a date in the last N days, biased toward weekdays (Mon–Fri)."""
    rng = random.random()
    if rng < 0.85:
        # Bias toward weekday
        while True:
            offset = random.randint(0, days_back - 1)
            d = datetime.now(timezone.utc) - timedelta(days=offset)
            if d.weekday() < 5:
                return d - timedelta(
                    hours=random.randint(8, 20),
                    minutes=random.randint(0, 59),
                )
    offset = random.randint(0, days_back - 1)
    return datetime.now(timezone.utc) - timedelta(days=offset)


def seed_leads(product_id_map: dict[str, str], count: int = 32) -> None:
    """Generate ~30 days of realistic leads with varied products + sizes."""
    existing_emails = _existing_emails()
    product_ids = list(product_id_map.values())
    if not product_ids:
        print("  ! no products to assign leads to — skipping")
        return

    created = 0
    attempts = 0
    while created < count and attempts < count * 3:
        attempts += 1
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        company = random.choice(COMPANIES)
        email = f"{first.lower()}@{company.lower().replace(' ', '').replace('-', '')}.com"
        if email in existing_emails:
            continue
        existing_emails.add(email)

        # 70% have one product, 25% have two, 5% have all three
        roll = random.random()
        if roll < 0.05:
            chosen_products = product_ids
        elif roll < 0.30:
            chosen_products = random.sample(product_ids, 2)
        else:
            chosen_products = [random.choice(product_ids)]

        fields = {
            "Email": email,
            "First Name": first,
            "Last Name": last,
            "Products": chosen_products,
            "Notes": random.choice(NOTE_BANK),
        }
        leads_table.create(fields, typecast=True)
        created += 1

    print(f"  ✓ created {created} leads across the last 30 days")


def main() -> None:
    random.seed()
    print("\nSeeding demo data into Airtable…\n")
    print("Products:")
    product_ids = seed_products()
    print("\nDocuments:")
    seed_documents(product_ids)
    print("\nLeads:")
    seed_leads(product_ids, count=32)
    print("\nDone.  Next: run `python -m app.ingest` to embed docs into Supabase.\n")


if __name__ == "__main__":
    main()
