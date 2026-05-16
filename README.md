# Sales Agent

A FastAPI-powered AI sales agent built on **Claude** (Opus 4.7), **Airtable**
(CRM), **Supabase** (vector RAG), and **Voyage AI** (embeddings). Answers
product questions with real testimonials, qualifies leads, sends booking links.

### URL: https://web-production-87c65.up.railway.app/

## Architecture

```
┌────────────┐    ┌──────────────┐    ┌──────────────────┐
│  Browser   │────│  FastAPI     │────│  Claude API      │
│  (widget)  │◄───│  /chat       │◄───│  (tool-calling)  │
└────────────┘    └──────┬───────┘    └────────┬─────────┘
                         │                     │
              ┌──────────┼──────────┐          │ tool_use
              │          │          │          ▼
          ┌───┴────┐ ┌───┴────┐ ┌───┴─────┐ ┌─────────┐
          │Airtable│ │Airtable│ │ Voyage  │ │  Tools  │
          │Products│ │ Leads  │ │ + Super │ │executor │
          └────────┘ └────────┘ │  base   │ └─────────┘
                                └─────────┘
```

The agent has 4 tools:

| Tool | What it does |
|---|---|
| `get_products` | Lists products from Airtable (name, price, ideal client) |
| `get_product_details` | Semantic search over docs/testimonials in Supabase |
| `save_lead` | Upserts a lead in Airtable Leads table |
| `send_booking_link` | Returns the buy-now / booking link for a product |

---

## 1. Airtable setup

Create three tables in your base.

### `Products`
| Field | Type |
|---|---|
| Product Name | Single line text |
| Slang | Long text *(alternative names / abbreviations)* |
| Description | Long text |
| Price | Number / Currency |
| Payment Schedule | Single select (Monthly / Yearly / One-time) |
| Ideal Client | Long text |
| Bad Client | Long text |
| Lead Magnet Link | URL |
| Buy Now Link | URL |
| Documents | Link to `Documents` (multiple) |

### `Leads`
| Field | Type |
|---|---|
| Email | Email *(primary)* |
| First Name | Single line text |
| Last Name | Single line text |
| Products | Link to `Products` (multiple) |
| Notes | Long text |
| Deal Size | Rollup of `Products → Price` (sum) |

### `Documents`
| Field | Type |
|---|---|
| Document ID | Autonumber |
| Source Media | Attachment |
| Source | Single select (School / YouTube / Zoom / etc) |
| Source URL | URL |
| Description | Long text |
| Context | Single select (Testimonial / Demo / Sales Call) |
| Content | Long text *(transcript / extracted text)* |
| Mime Type | Single line text |
| Indexed | Checkbox |

---

## 2. Supabase setup

In your Supabase project's SQL Editor, run `setup_supabase.sql`. This creates
the `documents` table with a `vector(1024)` column (matches Voyage's
`voyage-3.5-lite` output) and the `match_documents` RPC for similarity search.

---

## 3. Voyage AI key

Sign up at [voyageai.com](https://voyageai.com) — the free tier covers 200M
tokens, more than enough for sales-doc retrieval. Copy your API key into
`VOYAGE_API_KEY`.

---

## 4. Local development (Cursor)

```bash
# Python 3.10+ recommended (3.11 pinned for Railway)
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# fill in ANTHROPIC_API_KEY, AIRTABLE_API_KEY, SUPABASE_KEY, VOYAGE_API_KEY
```

Test connectivity:
```bash
python -m app.ingest      # pulls Airtable docs, embeds them, writes to Supabase
python -m app.main        # starts the chat at http://localhost:3000
```

Quick sanity check via curl:
```bash
curl -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What products do you offer?"}'
```

---

## 5. Deploy to Railway

### One-time setup
1. Push this repo to GitHub.
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**.
3. Pick the repo. Railway auto-detects Python via Nixpacks and uses
   `railway.json` for the start command.
4. Open the **Variables** tab and add each entry from your `.env`
   (Railway does **not** read `.env` files — they're set in the UI):

   ```
   ANTHROPIC_API_KEY
   AIRTABLE_API_KEY
   AIRTABLE_BASE_ID
   SUPABASE_URL
   SUPABASE_KEY
   VOYAGE_API_KEY
   ```

   `PORT` is injected by Railway automatically — don't set it.
5. Open **Settings** → **Networking** → **Generate Domain** to get a public URL.
6. The chat widget is live at the root of that URL; the API endpoint is `/chat`.

### Updating
Every push to your tracked branch triggers a redeploy. To re-index documents
after adding new rows in Airtable, either:

- run `python -m app.ingest` locally (it talks to the same Supabase), or
- open a Railway shell on the service and run the same command there.

### Health check
Railway pings `/health` after each deploy; the app returns `{"status": "ok"}`.

---

## 6. Customizing

- **Cheaper / faster model** — set `CLAUDE_MODEL=claude-sonnet-4-6` in env vars.
- **System prompt** — edit `SYSTEM_PROMPT` in `app/agent.py`.
- **Add tools** — append a schema to `TOOL_SCHEMAS` and a branch to
  `execute_tool()` in `app/tools.py`.
- **Production CORS** — replace `allow_origins=["*"]` in `app/main.py` with
  your real frontend origin.
- **Embed the widget on your site** — copy `static/index.html`, change
  `fetch('/chat')` to your Railway URL.

---

## Notes

- Audio/video transcription isn't included — paste transcripts into the
  `Content` field manually, or extend `app/ingest.py` to call Whisper.
- For WhatsApp / Telegram / Vapi: write a thin webhook that calls
  `run_agent(message, history)` and posts back. The agent core stays the same.
- Voyage's `input_type` matters: `document` when indexing, `query` when
  searching. The code handles this — don't change it unless you know why.
