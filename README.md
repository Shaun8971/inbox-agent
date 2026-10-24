# Inbox Agent

An AI agent that triages my Dartmouth Gmail, marks low-value email as read, sends a digest to Telegram, drafts replies on request, and adds calendar events from chat. It never sends email: the LLM judges, code acts, and I approve anything risky.

## Status
- Phase 0, Setup: done
- Phase 1, Read the inbox: done
- Phase 2, Triage and eval: next

## How it works (so far)
Gmail API (read-only) → fetch unread emails → extract and clean bodies → structured records

## Setup
1. `python3.13 -m venv .venv && source .venv/bin/activate`
2. `python -m pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in the gateway values
4. Google Cloud: enable the Gmail API, create an Internal OAuth desktop client, save it as `credentials.json` in the project root
5. `python -m nbstripout --install`
6. Run `notebooks/01_gmail_connect.ipynb`. The first run opens a browser sign-in

## Design decisions
- Least privilege: read-only access until actions need more
- Bodies capped at 8,000 characters for cost; truncation is recorded, never hidden
- Notebook outputs are stripped before commit so email content never reaches GitHub

## Limitations
- One API call per email (no batching yet)
- HTML-to-text can split sentences across lines
- Runs only on my laptop for now

## Roadmap
Triage and eval → Telegram digest → actions → drafting replies → calendar from chat → scheduling