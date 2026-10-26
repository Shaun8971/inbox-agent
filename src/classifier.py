"""Triage layer 2: LLM call 1, the classifier.

Sends one email to the LLM with the classifier prompt, then checks the answer before trusting it.
Anything malformed, or outside the allowed types, becomes "unsure" (the safe, visible default).
"""
import json
import re

from src.config import ROOT
from src.llm_client import call_llm

PROMPT_FILE = ROOT / "prompts" / "classifier.md"

# Types only the rules can assign. The LLM may never return these
RULE_ONLY_TYPES = {"event_newsletter", "canvas_routine", "canvas_prof_post", "canvas_due_dates", "calendar_accepted", "calendar_declined"}


def _neutralize_tags(text):
    """Turn any <email> or </email> written INSIDE the email into [email] / [/email],
    so the email can't fake the end of the boundary. re.IGNORECASE also catches </EMAIL> etc."""
    return re.sub(r"<(/?)email>", r"[\1email]", text, flags=re.IGNORECASE)


def _format_email(record):
    """Build the message the LLM sees: the email's fields wrapped in <email> tags."""
    body = record["body"] or record["snippet"]   # Image-only emails have no body; fall back to Gmail's preview
    fields = (
        f"From: {record['sender']}\n"
        f"To: {record['to']}\n"
        f"Cc: {record['cc']}\n"
        f"Subject: {record['subject']}\n"
        f"Date: {record['date']}\n"
        f"mass_mail: {str(record['is_mass_mail']).lower()}\n"        # true / false, matching the prompt's wording
        f"body_truncated: {str(record['body_truncated']).lower()}\n"
        f"\n{body}"
    )
    return f"<email>\n{_neutralize_tags(fields)}\n</email>"

def _unsure(reason, gist=""):
    """The safe fallback result: visible in the digest, and flagged as invalid so we can count failures."""
    return {"type": "unsure", "gist": gist, "reason": reason, "valid": False}


def _parse_reply(text, allowed_types):
    """Turn the LLM's reply into a checked result. Never trusts the reply blindly."""
    # Some models wrap JSON in ```json ... ``` fences; strip them if present
        # Find the JSON object even if the LLM wrote text around it (or code fences):
    # take everything from the first "{" to the last "}".
    # .find() gives the position of the first match, .rfind() the last; both return -1 if not found
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        return _unsure("Classifier reply contained no JSON object")
    cleaned = text[start:end + 1]   # Slice out just that part; +1 includes the closing }

    try:
        data = json.loads(cleaned)   # Text -> Python dictionary
    except json.JSONDecodeError:
        return _unsure("Classifier reply was not valid JSON")

    if not isinstance(data, dict):   # Valid JSON, but not the {...} shape we asked for
        return _unsure("Classifier reply was not a JSON object")

    gist = str(data.get("gist", ""))[:200]   # [:200] = hard length cap, enforced by code
    llm_type = data.get("type")
    if llm_type not in allowed_types:
        return _unsure(f"Classifier returned a type that isn't allowed: {llm_type}", gist)

    return {"type": llm_type, "gist": gist, "reason": str(data.get("reason", ""))[:150], "valid": True}

def classify(record, config, client):
    """Classify one email with LLM call 1.
    Returns: type, gist, reason, valid (False = we fell back to unsure), info (latency/tokens), raw_reply."""
    # All types in triage.yaml, minus the rule-only ones = the ten the LLM may choose
    allowed_types = set(config["types"]) - RULE_ONLY_TYPES

    text, info = call_llm(
        client,
        config["llm"]["model"],
        system=PROMPT_FILE.read_text(),   # Read fresh on every call, so prompt edits apply immediately
        user=_format_email(record),
        max_tokens=config["llm"]["classifier_max_tokens"],
    )

    result = _parse_reply(text, allowed_types)
    result["info"] = info        # Latency and token counts, for cost tracking
    result["raw_reply"] = text   # The original reply, useful when reviewing mistakes
    return result