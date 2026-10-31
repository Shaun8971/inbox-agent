"""One command that runs the whole agent once:
new unread email → triage → act on Skip emails → Telegram pings and digest → remember what was handled.

    python run.py            Dry run (shadow mode): nothing changes in Gmail, nothing is remembered
    python run.py --live     Live: skips are applied, and handled emails are remembered
"""
import argparse
from datetime import datetime

from src.actions import apply_actions
from src.config import load_config
from src.digest import _name, build_digest, save_number_map
from src.gmail_client import get_service
from src.llm_client import get_client
from src.pipeline import triage
from src.state import load_state, mark_processed, save_state
from src.telegram_client import send_message


def run(live=False, max_results=25, quiet = False):
    """Run the agent once. live=False (the default) is shadow mode."""
    config = load_config()
    service, client = get_service(), get_client()
    state = load_state()
    tag = "" if live else "🧪 DRY RUN · "   # Marks shadow-mode messages so they're never mistaken for real ones

    # 1. Decide every NEW unread email (already-handled ones are dropped before any LLM call)
    items = triage(service, client, config, max_results=max_results, state=state)

    # 2. Act on Skip emails. In a dry run, this only reports what it would do
    apply_actions(service, items, dry_run=not live)

    # 3. One ping per Act email, sent first so the important ones arrive on top.
    #    quiet=True (for clearing a backlog): no pings; Act emails go into the digest instead
    if not quiet:
        for it in items:
            if it["telegram"] == "ping":
                send_message(f"{tag}🔔 {_name(it['sender'])}: {it['gist'] or it['subject']}")

    # 4. One digest, sent only if it has at least one numbered line
    digest_items = items if quiet else [it for it in items if it["telegram"] != "ping"]
    text, number_map = build_digest(digest_items)
    if number_map:
        send_message(tag + text)
        save_number_map(number_map)

    # 5. Remember what was handled. Live runs only, and only valid results (invalid ones get retried)
    if live:
        for it in items:
            if it["valid"]:
                mark_processed(state, it)
        state["last_run"] = datetime.now().isoformat(timespec="seconds")
        save_state(state)

    # 6. One summary line, which becomes the log entry when this runs on a schedule
    counts = {a: sum(it["action"] == a for it in items) for a in ("act", "read", "skip")}
    print(f"{datetime.now():%Y-%m-%d %H:%M} | {'live' if live else 'dry run'} | new: {len(items)} | "
          f"act: {counts['act']} | read: {counts['read']} | skip: {counts['skip']}")


if __name__ == "__main__":
    # This block runs only when the file is run directly ("python run.py"), not when it's imported.
    # argparse reads the options typed after the command, such as --live
    parser = argparse.ArgumentParser(description="Run the inbox agent once.")
    parser.add_argument("--live", action="store_true", help="Apply actions and remember handled emails")
    parser.add_argument("--max", type=int, default=25, help="Most unread emails to look at per run")
    parser.add_argument("--quiet", action="store_true", help="No pings: use when clearing a backlog")
    args = parser.parse_args()

    try:
        run(live=args.live, max_results=args.max, quiet=args.quiet)
    except Exception as e:
        # Monitoring: a failed scheduled run tells you on Telegram instead of failing silently
        send_message(f"⚠️ Inbox agent run failed: {type(e).__name__}: {str(e)[:300]}")
        raise   # Re-raise, so the full error also shows in the terminal or log