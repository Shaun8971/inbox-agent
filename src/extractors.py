"""Triage layer 3: LLM call 2, the extractors.

extract_events reads one email and returns only the events that match the interest profile in triage.yaml.
Like the classifier, it never trusts the reply: anything malformed becomes "no events" plus a flag.
"""
import json
import re
from datetime import datetime

from src.classifier import _format_email   # Same <email> wrapping and tag neutralization as call 1
from src.config import ROOT
from src.llm_client import call_llm

EVENTS_PROMPT = ROOT / "prompts" / "events.md"
EVENT_FIELDS = ["title", "when", "where", "register_by", "why", "fit"]   # The only fields we keep
MAX_EVENTS = 5   # Hard cap per email, so one long newsletter can't flood the digest


def _interest_profile_text(config):
    """Turn Section 4 of triage.yaml into plain sentences for the prompt."""
    p = config["interests"]
    lines = ["Requirements (ALL must be met):"] + [f"- {x}" for x in p["requirements"]]
    lines += ["Include only these kinds:"] + [f"- {x}" for x in p["include"]]
    lines += ["Never include:"] + [f"- {x}" for x in p["exclude"]]
    lines += [f"Exception: {p['exception']}",
              f"When unclear: {p['when_unclear']}",
              f"If the duration isn't stated: {p['duration_unknown']}"]
    return "\n".join(lines)   # Join everything into one block of text, one item per line


def _fill(template, values):
    """Replace each {name} placeholder in the prompt with its value.
    We use .replace instead of Python's .format, because the prompt's JSON example is full of { } braces,
    which .format would mistake for placeholders and crash on."""
    for name, value in values.items():
        template = template.replace("{" + name + "}", value)
    return template


def _strip_links(text):
    """Remove any web address: a code-level guarantee on top of the prompt's 'no links' rule."""
    return re.sub(r"https?://\S+", "[link removed]", text)   # \S+ = everything up to the next space


def _parse_events(text):
    """Turn the reply into a checked list of events. Returns (events, valid)."""
    start, end = text.find("{"), text.rfind("}")   # Same outermost-{ } approach as the classifier
    if start == -1 or end < start:
        return [], False
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return [], False
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        return [], False   # Valid JSON, but not the {"events": [...]} shape we asked for

    events = []
    for e in data["events"][:MAX_EVENTS]:            # [:MAX_EVENTS] = keep at most 5
        if isinstance(e, dict) and e.get("title"):   # Skip anything that isn't a proper event with a name
            # Keep only the known fields, as short, link-free text (150 characters max each)
                        # Keep only the known fields, as short, link-free text (150 characters max each)
            event = {f: _strip_links(str(e.get(f, "")))[:150] for f in EVENT_FIELDS}
            # Anything other than a clear "yes" becomes "maybe", so you're asked rather than it being dropped
            if event["fit"].lower() != "yes":
                event["fit"] = "maybe"
            events.append(event)
    return events, True


def extract_events(record, config, client):
    """LLM call 2 for event emails. Returns: events (list), valid (False = unusable reply), info, raw_reply."""
    system = _fill(EVENTS_PROMPT.read_text(), {
        "today": datetime.now().strftime("%A, %B %d, %Y"),   # e.g. Monday, October 26, 2026
        "interest_profile": _interest_profile_text(config),
    })
    text, info = call_llm(client, config["llm"]["model"], system=system, user=_format_email(record),
                          max_tokens=config["llm"].get("extractor_max_tokens", 600))   # Default 600 if not in config
    events, valid = _parse_events(text)
    return {"events": events, "valid": valid, "info": info, "raw_reply": text}

GIST_PROMPT = ROOT / "prompts" / "gist.md"

def extract_gist(record, config, client):
    """LLM call 2 for emails that need a one-line summary (e.g. Canvas professor posts).
    Returns: gist (text), valid (False = unusable reply), info, raw_reply."""
    text, info = call_llm(client, config["llm"]["model"], system=GIST_PROMPT.read_text(),
                          user=_format_email(record), max_tokens=200)

    # Same checking approach as the other extractors: find the outermost { }, then read it as JSON
    gist, valid = "", False
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, dict) and data.get("gist"):
                gist, valid = _strip_links(str(data["gist"]))[:200], True   # Link-free, 200 characters max
        except json.JSONDecodeError:
            pass   # Unusable reply: gist stays empty and valid stays False
    return {"gist": gist, "valid": valid, "info": info, "raw_reply": text}

DUE_PROMPT = ROOT / "prompts" / "due_dates.md"
DUE_FIELDS = ["course", "title", "due", "due_iso"]   # The only fields we keep
MAX_DUE_ITEMS = 15                                    # Hard cap per summary email


def extract_due_dates(record, config, client):
    """LLM call 2 for Canvas due-date summaries. Returns: items (list), valid, info, raw_reply.
    due_iso is a machine-readable date for the calendar; it's validated properly in Phase 5."""
    system = _fill(DUE_PROMPT.read_text(), {"today": datetime.now().strftime("%A, %B %d, %Y")})
    text, info = call_llm(client, config["llm"]["model"], system=system, user=_format_email(record),
                          max_tokens=config["llm"].get("extractor_max_tokens", 600))

    # Same checking approach: outermost { }, read as JSON, keep only well-formed items with a title
    items, valid = [], False
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, dict) and isinstance(data.get("items"), list):
                valid = True
                for d in data["items"][:MAX_DUE_ITEMS]:
                    if isinstance(d, dict) and d.get("title"):
                        items.append({f: _strip_links(str(d.get(f, "")))[:150] for f in DUE_FIELDS})
        except json.JSONDecodeError:
            pass   # Unusable reply: no items, valid stays False
    return {"items": items, "valid": valid, "info": info, "raw_reply": text}