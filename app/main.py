"""FastAPI server. Chat + business-metrics dashboard."""
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent import run_agent
from app.config import PORT
from app.metrics import compute_metrics

app = FastAPI(title="Sales Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, Any]]] = None


class WaitlistRequest(BaseModel):
    name: str
    company: Optional[str] = None
    email: str
    phone: Optional[str] = None
    wants_demo: bool = False
    message: Optional[str] = None


@app.get("/")
def root():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest):
    """Agent endpoint. Returns just {reply, history} — clean for the UI."""
    result = run_agent(req.message, history=req.history)
    return JSONResponse({"reply": result["reply"], "history": result["history"]})


@app.post("/waitlist")
def waitlist(req: WaitlistRequest):
    """Capture waitlist signups directly into the Leads table.

    Company, phone, and demo preference are appended into the Notes field as
    structured text so we don't need new Airtable columns. If you later add
    dedicated 'Company' and 'Phone' fields to Airtable, move those out of Notes.
    """
    from app import airtable_client

    parts = req.name.strip().split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    note_lines = ["[Waitlist signup]"]
    if req.company:
        note_lines.append(f"Company: {req.company}")
    if req.phone:
        note_lines.append(f"Phone: {req.phone}")
    if req.wants_demo:
        note_lines.append("Wants demo call: yes")
    if req.message:
        note_lines.append(f"Message: {req.message}")
    notes = "\n".join(note_lines)

    try:
        record = airtable_client.upsert_lead(
            email=req.email,
            first_name=first_name,
            last_name=last_name,
            notes=notes,
        )
        return JSONResponse({"ok": True, "id": record["id"]})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.get("/metrics")
def metrics():
    """Business metrics for the dashboard."""
    try:
        return JSONResponse(compute_metrics())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, reload=True)