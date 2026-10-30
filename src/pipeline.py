"""The triage pipeline: runs each email through rules, the classifier, and the extractors,
and returns one decided item per email. Read-only: it changes nothing in Gmail (that's Phase 4)."""
from src.classifier import classify
from src.extractors import extract_events, extract_gist, extract_due_dates
from src.gmail_client import fetch_unread
from src.rules import apply_rules
from src.state import is_new


def triage_one(record, config, client):
    """Decide one email: its type, who decided, the final action, and anything extracted for the digest."""
    # ---- Layer 1: rules. Layer 2: the classifier, only if no rule matched ----
    rule_type = apply_rules(record, config)
    if rule_type:
        etype, source, gist, valid = rule_type, "rule", "", True
    else:
        res = classify(record, config, client)
        etype, source, gist, valid = res["type"], "llm", res["gist"], res["valid"]

    settings = config["types"][etype]   # This type's row in triage.yaml: action, extract, telegram
    events = []
    due = []

    # ---- Layer 3: extractors, only for types that need one ----
    if settings["extract"] == "events":
        ex = extract_events(record, config, client)
        events = ex["events"]
        valid = valid and ex["valid"]   # One unusable reply anywhere marks the whole item as invalid
    elif settings["extract"] == "gist":
        ex = extract_gist(record, config, client)
        gist = ex["gist"] or record["snippet"]   # If the reply was unusable, fall back to Gmail's preview
        valid = valid and ex["valid"]    
    elif settings["extract"] == "due_dates":
        ex = extract_due_dates(record, config, client)
        due = ex["items"]
        valid = valid and ex["valid"]   # If extraction fails, the safety rule keeps the summary visible
    
    # ---- Resolve the final action ----
    action = settings["action"]
    if action == "read_if_match":
        action = "read" if events else "skip"   # Keep it only if the extractor found a matching event
    if not valid:
        action = "read"   # Safety rule: an unusable reply never gets an email archived

    return {
        "id": record["id"], "sender": record["sender"], "subject": record["subject"],
        "type": etype, "source": source, "action": action, "telegram": settings["telegram"],
        "gist": gist, "events": events, "valid": valid, "due": due,
    }

def triage(service, client, config, max_results=25, state=None):
    """Fetch unread email (minus exclusions) and decide each one.
    If state is given, emails handled in an earlier run are dropped BEFORE any LLM call."""
    records = fetch_unread(service, config, max_results=max_results)
    if state is not None:
        records = [r for r in records if is_new(state, r["id"])]   # Keep only emails not seen before
    return [triage_one(r, config, client) for r in records]