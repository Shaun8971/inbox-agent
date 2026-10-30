"""Gmail access: sign-in, fetching unread emails, and turning raw emails into clean records.

Read-only for now (gmail.readonly). Phase 4 upgrades the permission when the agent
starts marking emails as read and archiving them.
"""
import base64
import html
import re

from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.config import CREDENTIALS_FILE, TOKEN_FILE   # Paths now come from one place

# Read, label, mark as read, and archive. This permission technically also allows sending,
# which is why our code contains no send function at all: the guard lives in code
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Max characters of body kept per email (~2,000 tokens). Older quoted replies sit at the bottom, so they're cut first
MAX_BODY_CHARS = 8000

# =====================================================================
# SIGN-IN
# =====================================================================

def get_credentials():
    """Return valid Google credentials, opening the browser to sign in only if needed."""
    creds = None

    # Reuse the saved login if you've signed in before
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # The short-term pass (access token) expired: quietly get a new one using the refresh token
            creds.refresh(Request())
        else:
            # First time, or the saved login is unusable: sign in through the browser
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)   # port=0 = use any free port on this laptop
        TOKEN_FILE.write_text(creds.to_json())       # Save the login for next time

    return creds


def get_service():
    """Return a ready-to-use Gmail connection.
    If you hit 'Can't assign requested address' after a network change, just call this again."""
    return build("gmail", "v1", credentials=get_credentials())

# =====================================================================
# BODY EXTRACTION (email parts are nested like Russian dolls)
# =====================================================================

def _decode(data):
    """Turn Gmail's encoded text (URL-safe base64) back into normal readable text."""
    padded = data + "=" * (-len(data) % 4)            # Add back any missing "=" fillers (base64 works in blocks of 4)
    raw_bytes = base64.urlsafe_b64decode(padded)      # Unpack into raw bytes
    return raw_bytes.decode("utf-8", errors="replace")   # Bytes -> text; a broken character becomes a placeholder


def _find_part(payload, mime_type):
    """Search the nested parts for the first one of this type (e.g. "text/plain"), skipping attachments.
    Returns the still-encoded content, or None if not found."""
    is_right_type = payload.get("mimeType") == mime_type
    is_attachment = bool(payload.get("filename"))      # Attachments have a filename; the email's own text doesn't
    data = payload.get("body", {}).get("data")
    if is_right_type and not is_attachment and data:
        return data

    # Not this doll: search each inner doll (the function calls itself, which is called recursion)
    for part in payload.get("parts", []):
        found = _find_part(part, mime_type)
        if found:
            return found
    return None


def extract_body(payload):
    """Return the email's readable text: plain text if available, otherwise HTML with the tags stripped.
    Returns "" if there's no text at all (e.g. an image-only email)."""
    plain = _find_part(payload, "text/plain")
    if plain:
        text = _decode(plain)
    else:
        html_data = _find_part(payload, "text/html")
        if not html_data:
            return ""
        # Keep only the visible text. separator="\n" stops paragraphs from running together
        text = BeautifulSoup(_decode(html_data), "html.parser").get_text(separator="\n")

    text = re.sub(r"\n\s*\n+", "\n\n", text)   # Collapse runs of blank lines into one
    return text.strip()

# =====================================================================
# FETCHING
# =====================================================================

def build_query(config, base="is:unread in:inbox"):
    """Build a Gmail search: the base search, minus every excluded label in triage.yaml.
    base defaults to unread inbox email (what the agent processes).
    The eval passes a different base (e.g. all recent inbox email); exclusions always apply."""
    # Each excluded label becomes -label:"Name". The minus sign means "not"
    exclusions = " ".join(f'-label:"{name}"' for name in config.get("excluded_labels", []))
    return f"{base} {exclusions}".strip()

def _to_record(full):
    """Turn one raw Gmail message (format="full") into our clean dictionary.
    Shared by fetch_unread and fetch_by_id, so both always produce identical records."""
    # Header lookup table, with names lowercased because senders write "Cc"/"CC"/"cc" inconsistently
    headers = {h["name"].lower(): h["value"] for h in full["payload"].get("headers", [])}
    body = extract_body(full["payload"])
    return {
        "id": full["id"],                                    # Needed later to act on the email
        "thread_id": full["threadId"],                       # Links the email to its conversation
        "sender": headers.get("from", "(unknown sender)"),
        "to": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "subject": headers.get("subject", "(no subject)"),
        "date": headers.get("date", ""),
        "is_mass_mail": "list-unsubscribe" in headers,       # A hint for the LLM, never a decision on its own
        "snippet": html.unescape(full.get("snippet", "")),
        "body": body[:MAX_BODY_CHARS],                       # Apply the cost cap
        "body_truncated": len(body) > MAX_BODY_CHARS,        # Record the cut, so we never claim we saw everything
        "labels": full.get("labelIds", []),
    }


def fetch_by_id(service, msg_id):
    """Fetch one email by its Gmail ID, as a clean record.
    Only use IDs that came from a build_query search, so excluded labels stay excluded."""
    full = service.users().messages().get(userId="me", id=msg_id, format="full").execute(num_retries=5)
    return _to_record(full)


def fetch_unread(service, config, max_results=10, base="is:unread in:inbox"):
    """Fetch emails matching the search (default: unread inbox), minus excluded labels, as clean records."""
    # Call 1 (LIST): IDs only. num_retries = automatic backoff on speed-limit errors
    response = service.users().messages().list(
        userId="me", q=build_query(config, base), maxResults=max_results
    ).execute(num_retries=5)

    # Call 2 (GET) for each ID, through fetch_by_id. Missing "messages" key = nothing found
    return [fetch_by_id(service, m["id"]) for m in response.get("messages", [])]