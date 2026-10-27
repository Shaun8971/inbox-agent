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
- Test set is small (40 emails); a perfect score means "probably under 1 in 13 wrong," not "perfect"
- Temperature can't be set in the current Anthropic SDK, so answers may vary slightly between runs
- The gateway caches the full request, which is never reused; prompt-only caching is a planned optimization

## Roadmap
Triage and eval → Telegram digest → actions → drafting replies → calendar from chat → scheduling

## Status
- Phase 0, Setup: done
- Phase 1, Read the inbox: done
- Phase 2, Triage and eval: done
- Phase 3, Telegram digest: next

## How it works (so far)
Gmail (read-only) → fetch unread, minus excluded labels → rules (known senders, Canvas patterns, calendar replies) → LLM classifier, only if no rule matched → checked type + one-line gist

## Project structure
- `config/triage.yaml`: rules, types and their actions, interest profile, LLM settings
- `prompts/classifier.md`: the classifier prompt
- `src/gmail_client.py`: sign-in, fetching, body extraction
- `src/rules.py`: deterministic rules
- `src/llm_client.py`: gateway connection, latency and token tracking
- `src/classifier.py`: LLM call 1 with reply checking
- `src/evaluate.py`: scores the pipeline against the frozen answer key