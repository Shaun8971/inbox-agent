"""Remembers which emails the agent has already handled, so no email is classified, acted on,
or pinged twice. Stored in data/state.json, which is ignored by Git."""
import json
from datetime import datetime

from src.config import ROOT

STATE_FILE = ROOT / "data" / "state.json"
MAX_REMEMBERED = 5000   # Keep the most recent 5,000; older emails are long gone from the unread inbox


def load_state():
    """Read the saved state, or start fresh if this is the first run."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"processed": {}, "last_run": None}


def save_state(state):
    """Write the state back to disk, keeping only the most recent entries."""
    processed = state["processed"]
    if len(processed) > MAX_REMEMBERED:
        # Dictionaries keep the order items were added in, so the last 5,000 are the newest
        state["processed"] = dict(list(processed.items())[-MAX_REMEMBERED:])
    STATE_FILE.parent.mkdir(exist_ok=True)   # Make sure data/ exists
    STATE_FILE.write_text(json.dumps(state, indent=2))


def is_new(state, email_id):
    """True if the agent hasn't handled this email in an earlier run."""
    return email_id not in state["processed"]


def mark_processed(state, item):
    """Record that an email was handled: what was decided, and when."""
    state["processed"][item["id"]] = {
        "type": item["type"],
        "action": item["action"],
        "at": datetime.now().isoformat(timespec="seconds"),   # e.g. 2026-10-28T09:00:00
    }