"""Builds the Telegram digest from decided items, and remembers what each number refers to,
so later commands like "draft reply to #3" know which email #3 is."""
import json
from collections import Counter
from datetime import datetime
from email.utils import parseaddr

from src.config import ROOT

LAST_DIGEST_FILE = ROOT / "data" / "last_digest.json"   # Number -> email ID, for chat commands later


def _name(sender):
    """Display name from a From line, falling back to the address: 'Prof. Smith <s@x.edu>' -> 'Prof. Smith'."""
    name, address = parseaddr(sender)
    return name or address


def build_digest(items):
    """Turn decided items into (digest_text, number_map). number_map links each number to its email ID."""
    sections = {"ACT (still unread)": [], "READ": [], "EVENTS": [], "FYI (archived)": []}
    number_map = {}
    n = 0   # One running number across all sections, so every line has a unique #

    def add(section, text, email_id):
        """Number a line, put it in its section, and remember which email it belongs to."""
        nonlocal n   # Update the n defined above, instead of creating a new one inside this function
        n += 1
        sections[section].append(f"{n}. {text}")
        number_map[n] = email_id

    for it in items:
        # The line shows the sender and the gist, or the subject if there's no gist
        line = f"{_name(it['sender'])}: {it['gist'] or it['subject']}"
        if it["type"] == "unsure":
            line += "  [unsure, please check]"
        if it["telegram"] == "ping":
            add("ACT (still unread)", line, it["id"])
        elif it["telegram"] == "digest_line":
            # Read items stay in the inbox; skipped ones with a gist (e.g. Dartmouth notices) go under FYI
            add("READ" if it["action"] == "read" else "FYI (archived)", line, it["id"])

        # Events from newsletters or single invites, each with its own number
        for e in it["events"]:
            mark = "✅" if e["fit"] == "yes" else "❓"
            details = " · ".join(x for x in [e["when"], e["where"]] if x)   # Leave out empty parts
            reg = f" · register by {e['register_by']}" if e["register_by"] else ""
            ask = "  interested?" if e["fit"] == "maybe" else ""
            add("EVENTS", f"{mark} {e['title']} · {details}{reg}{ask}", it["id"])

    # ---- Assemble the message: header, the non-empty sections, then the skipped count by type ----
    lines = [f"📬 Inbox digest · {datetime.now().strftime('%a %-I:%M %p')}"]   # e.g. Tue 2:00 PM
    for title, entries in sections.items():
        if entries:
            lines += ["", title] + entries   # "" adds a blank line before each section
    skipped = Counter(it["type"].replace("_", " ") for it in items if it["action"] == "skip")
    if skipped:
        breakdown = ", ".join(f"{t} {c}" for t, c in skipped.most_common())
        lines += ["", f"Skipped: {sum(skipped.values())} ({breakdown})"]
    return "\n".join(lines), number_map


def save_number_map(number_map):
    """Remember what each number in the latest digest refers to. Saved in data/, so it stays off GitHub."""
    LAST_DIGEST_FILE.write_text(json.dumps(number_map, indent=2))