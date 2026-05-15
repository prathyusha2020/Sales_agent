"""Claude tool-calling loop for the sales agent."""
from typing import Any, Dict, List

from anthropic import Anthropic

from app.config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from app.tools import TOOL_SCHEMAS, execute_tool

_client = Anthropic(api_key=ANTHROPIC_API_KEY)


SYSTEM_PROMPT = """You are an internal sales operations copilot. Your users
are salespeople, the founder, and ops staff — never customers. Help them find
lead info, summarize the pipeline, recall product material, log notes, and
draft follow-ups.

Tool routing:
- "who is X / find X / show me leads about X"  → search_leads
- "tell me more / details on lead Y"           → get_lead
- "leads this week / today / latest"           → list_recent_leads
- "pipeline / how are we doing / breakdown"    → pipeline_summary
- "what do we say about X / testimonials"      → search_knowledge_base
- "log a note / write down / remember that"    → log_note
- "draft a follow-up / email her about"        → draft_followup_email

How to format replies:
- Be direct. Skip preambles like "Sure, I'll look that up." Just answer.
- For lists of leads or items, use bullets (•). Bold the name in **markdown**.
- For currency, use $ with commas: $8,500 — never raw numbers like 8500.
- ALWAYS show the lead's record ID in `(rec...)` form when you mention a
  lead by name, so the user can reference them next.
- Pipeline summaries get short paragraph + bulleted breakdown.
- After answering, suggest ONE relevant next action when it fits — e.g.
  "Want me to draft a follow-up to Priya?" or "Should I log that call?"
  Don't suggest more than one. Skip it when the user is just browsing.

What NOT to do:
- Don't make up data. If a tool returns nothing, say so plainly.
- Don't paste raw record IDs without context — always with a name.
- Don't ask multiple clarifying questions at once. One question, max.
- Don't repeat the user's question back to them before answering.
"""


def run_agent(
    user_message: str,
    history: List[Dict[str, Any]] | None = None,
    max_turns: int = 8,
) -> Dict[str, Any]:
    """Run one user turn through the agent loop."""
    messages: List[Dict[str, Any]] = list(history or [])
    messages.append({"role": "user", "content": user_message})

    for _ in range(max_turns):
        response = _client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        # Persist the assistant turn as plain dicts (JSON-safe + valid for next call).
        assistant_content = [block.model_dump() for block in response.content]
        messages.append({"role": "assistant", "content": assistant_content})

        if response.stop_reason != "tool_use":
            text = "".join(
                block.text for block in response.content if block.type == "text"
            ).strip()
            return {"reply": text, "history": messages}

        # Execute every tool_use block in this turn and feed results back.
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input or {})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
        messages.append({"role": "user", "content": tool_results})

    return {
        "reply": "I'm having trouble completing that request. Could you rephrase?",
        "history": messages,
    }
