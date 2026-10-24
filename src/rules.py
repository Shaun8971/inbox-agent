"""Triage layer 1: deterministic rules.

apply_rules returns a type when a rule is certain, or None so that LLM call 1 decides.
Rules are high precision, low coverage: they only fire when they can't be wrong.
"""
from email.utils import parseaddr   # Python's built-in tool for reading email address lines


def _address(sender):
    """Return just the email address from a From line, in lowercase.
    Example: 'Vox Daily <Vox@Dartmouth.edu>' -> 'vox@dartmouth.edu'
    Lowercase because addresses aren't case-sensitive, but senders write them inconsistently."""
    # parseaddr splits a From line into (display name, address). [1] takes the address
    return parseaddr(sender)[1].lower()


def apply_rules(record, config):
    """Return the type decided by a rule, or None if no rule matches.

    record = one email with at least "sender" and "subject"
    config = the loaded triage.yaml settings
    """
    rules = config["rules"]
    sender = _address(record["sender"])
    subject = record["subject"].lower()   # Lowercase so phrase matching ignores capitals

    # ---- Rule 1: known event-newsletter senders ----
    newsletter_senders = [s.lower() for s in rules["event_newsletter_senders"]]
    if sender in newsletter_senders:
        return "event_newsletter"

    # ---- Rule 2: Canvas emails, sorted by subject phrase ----
    if sender == rules["canvas_sender"].lower():
        # Check each Canvas type in the order written in the config. The first phrase that matches wins
        for canvas_type, phrases in rules["canvas_subject_phrases"].items():
            if any(p.lower() in subject for p in phrases):
                return canvas_type
        return None   # A Canvas email no phrase matched: let LLM call 1 decide (the safe default)

    # ---- No rule matched ----
    return None