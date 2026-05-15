
from __future__ import annotations

import sys
from typing import Any

from pyairtable import Api

from app.config import AIRTABLE_API_KEY, AIRTABLE_BASE_ID


PRODUCTS_FIELDS: list[dict[str, Any]] = [
    {"name": "Product Name", "type": "singleLineText"},
    {"name": "Slang", "type": "multilineText"},
    {"name": "Description", "type": "multilineText"},
    {
        "name": "Price",
        "type": "number",
        "options": {"precision": 2},
    },
    {
        "name": "Payment Schedule",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "Monthly"},
                {"name": "Yearly"},
                {"name": "One-time"},
                {"name": "Per mile"},
                {"name": "Per container"},
            ]
        },
    },
    {"name": "Ideal Client", "type": "multilineText"},
    {"name": "Bad Client", "type": "multilineText"},
    {"name": "Lead Magnet Link", "type": "url"},
    {"name": "Buy Now Link", "type": "url"},
]


DOCUMENTS_FIELDS: list[dict[str, Any]] = [
    {"name": "Document ID", "type": "singleLineText"},
    {"name": "Source Media", "type": "multipleAttachments"},
    {
        "name": "Source",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "School"},
                {"name": "YouTube"},
                {"name": "Zoom"},
                {"name": "Google Drive"},
            ]
        },
    },
    {"name": "Source URL", "type": "url"},
    {"name": "Description", "type": "multilineText"},
    {
        "name": "Context",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "Testimonial"},
                {"name": "Demo"},
                {"name": "Sales Call"},
                {"name": "Client Call"},
            ]
        },
    },
    {"name": "Content", "type": "multilineText"},
    {"name": "Mime Type", "type": "singleLineText"},
    {"name": "Indexed", "type": "checkbox", "options": {"icon": "check", "color": "greenBright"}},
]


LEADS_FIELDS: list[dict[str, Any]] = [
    {"name": "Email", "type": "email"},
    {"name": "First Name", "type": "singleLineText"},
    {"name": "Last Name", "type": "singleLineText"},
    {"name": "Notes", "type": "multilineText"},
]


def _existing_field_names(table) -> set[str]:
    schema = table.schema(force=True)
    return {f.name for f in schema.fields}


def _ensure_field(table, spec: dict[str, Any], existing: set[str]) -> None:
    """Create a field on `table` if it doesn't already exist."""
    if spec["name"] in existing:
        print(f"    · field '{spec['name']}' exists")
        return
    options = spec.get("options")
    if options is not None:
        table.create_field(
            name=spec["name"], field_type=spec["type"], options=options
        )
    else:
        table.create_field(name=spec["name"], field_type=spec["type"])
    print(f"    ✓ field '{spec['name']}' created")


def _find_table(base, name: str):
    """Return the table object if it exists, else None."""
    try:
        schema = base.schema(force=True)
        for t in schema.tables:
            if t.name == name:
                return base.table(name)
    except Exception:
        pass
    return None


def _ensure_table(base, name: str, primary_field: dict[str, Any]):
    """Create a table if it doesn't exist. Returns the table object."""
    existing = _find_table(base, name)
    if existing is not None:
        print(f"  · table '{name}' exists")
        return existing

    options = primary_field.get("options")
    field_spec: dict[str, Any] = {
        "name": primary_field["name"],
        "type": primary_field["type"],
    }
    if options is not None:
        field_spec["options"] = options
    base.create_table(name=name, fields=[field_spec])
    print(f"  ✓ table '{name}' created")
    return base.table(name)


def _try_rename_default_table(base) -> None:
    """Airtable auto-creates 'Table 1' when you make a new base.
    If it exists and 'Products' doesn't, rename it."""
    schema = base.schema(force=True)
    names = {t.name for t in schema.tables}
    if "Products" in names:
        return
    if "Table 1" not in names:
        return
    for t in schema.tables:
        if t.name == "Table 1":
            t.name = "Products"
            t.save()
            print("  ✓ renamed default 'Table 1' to 'Products'")
            # Also rename the default first column ('Name' → 'Product Name')
            schema_after = base.table("Products").schema(force=True)
            for f in schema_after.fields:
                if f.name == "Name":
                    f.name = "Product Name"
                    f.save()
                    print("    ✓ renamed default 'Name' column to 'Product Name'")
                    break
            return


def main() -> None:
    print(f"\nBootstrapping schema in base {AIRTABLE_BASE_ID}…\n")
    api = Api(AIRTABLE_API_KEY)
    base = api.base(AIRTABLE_BASE_ID)

    # Sanity check — can we read the base?
    try:
        base.schema(force=True)
    except Exception as exc:
        print(f"ERROR: cannot read base schema: {exc}")
        print("Check that:")
        print("  - AIRTABLE_BASE_ID is correct in .env")
        print("  - your token has schema.bases:read scope")
        print("  - your token has access to this specific base")
        sys.exit(1)

    print("Products table:")
    _try_rename_default_table(base)
    products = _ensure_table(
        base, "Products", primary_field={"name": "Product Name", "type": "singleLineText"}
    )
    existing = _existing_field_names(products)
    for spec in PRODUCTS_FIELDS:
        if spec["name"] == "Product Name":
            continue
        _ensure_field(products, spec, existing)

    print("\nDocuments table:")
    documents = _ensure_table(
        base, "Documents", primary_field={"name": "Document ID", "type": "singleLineText"}
    )
    existing = _existing_field_names(documents)
    for spec in DOCUMENTS_FIELDS:
        if spec["name"] == "Document ID":
            continue
        _ensure_field(documents, spec, existing)

    print("\nLeads table:")
    leads = _ensure_table(
        base, "Leads", primary_field={"name": "Email", "type": "email"}
    )
    existing = _existing_field_names(leads)
    for spec in LEADS_FIELDS:
        if spec["name"] == "Email":
            continue
        _ensure_field(leads, spec, existing)

    print("\nLinked-record fields:")
    products_id = products.schema(force=True).id
    documents_id = documents.schema(force=True).id

    # Products → Documents (multiple)
    if "Documents" not in _existing_field_names(products):
        products.create_field(
            name="Documents",
            field_type="multipleRecordLinks",
            options={"linkedTableId": documents_id},
        )
        print("  ✓ Products.Documents → Documents (linked, multiple)")
    else:
        print("  · Products.Documents already linked")

    # Leads → Products (multiple)
    if "Products" not in _existing_field_names(leads):
        leads.create_field(
            name="Products",
            field_type="multipleRecordLinks",
            options={"linkedTableId": products_id},
        )
        print("  ✓ Leads.Products → Products (linked, multiple)")
    else:
        print("  · Leads.Products already linked")

    print("\n✓ Schema ready.")
    print("\nNext:")
    print("  python -m app.seed_data    # add demo products + 30 days of leads")
    print("  python -m app.ingest       # embed testimonials into Supabase")
    print("  python -m app.main         # start the server\n")


if __name__ == "__main__":
    main()