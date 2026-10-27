"""Evaluation: re-score the triage pipeline against the frozen answer key (data/test_set.json).

Run this after every change to the rules, prompt, or config, and compare with earlier runs.
Each run is appended as one line to data/eval_history.jsonl, which becomes the validation log.
"""
import json
from datetime import datetime

from src.classifier import classify
from src.config import ROOT
from src.gmail_client import fetch_by_id
from src.rules import apply_rules

TEST_SET_FILE = ROOT / "data" / "test_set.json"
HISTORY_FILE = ROOT / "data" / "eval_history.jsonl"
HIDES = {"skip", "read_if_match"}   # Actions that can end with the email archived


def run_eval(service, client, config, note=""):
    """Run the triage pipeline on every email in the answer key, print a report, and log the run.
    note = a short label for this run, e.g. "added optional_opportunity"."""
    test_set = json.loads(TEST_SET_FILE.read_text())

    # A type's action from the config. An unknown type counts as "read" (visible), the safe assumption
    action_of = lambda t: config["types"].get(t, {}).get("action", "read")

    # ---- 1. Run the real pipeline on each email: rules first, LLM only if no rule matches ----
    results = []
    for item in test_set:
        record = fetch_by_id(service, item["id"])
        rule_type = apply_rules(record, config)
        if rule_type:
            predicted, source, info, valid = rule_type, "rule", None, True
        else:
            res = classify(record, config, client)
            predicted, source, info, valid = res["type"], "llm", res["info"], res["valid"]
        # {**item, ...} = copy everything from the answer-key entry, then add the new fields
        results.append({**item, "predicted": predicted, "source": source, "info": info, "valid": valid})

    # ---- 2. Sort into right and wrong, and find the costly mistakes ----
    wrong = [r for r in results if r["predicted"] != r["correct_type"]]
    hidden = [r for r in wrong
              if action_of(r["predicted"]) in HIDES and action_of(r["correct_type"]) not in HIDES]
    llm = [r for r in results if r["source"] == "llm"]
    llm_wrong = [r for r in llm if r["predicted"] != r["correct_type"]]

    # ---- 3. The summary: one record per run, saved to the history ----
    summary = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),   # e.g. 2026-10-26T15:42:10
        "note": note,
        "emails": len(results),
        "accuracy": round(1 - len(wrong) / len(results), 3),
        "llm_accuracy": round(1 - len(llm_wrong) / len(llm), 3) if llm else None,
        "decided_by_rules": len(results) - len(llm),
        "wrongly_hidden": len(hidden),
        "fallbacks": sum(not r["valid"] for r in results),
        "avg_input_tokens": round(sum(r["info"]["input_tokens"] for r in llm) / len(llm)) if llm else 0,
        "avg_latency_s": round(sum(r["info"]["latency_s"] for r in llm) / len(llm), 2) if llm else 0,
    }

    # ---- 4. The report ----
    print(f"Accuracy: {summary['accuracy']:.0%} ({len(results) - len(wrong)}/{len(results)})  |  "
          f"LLM only: {len(llm) - len(llm_wrong)}/{len(llm)}  |  Decided by rules: {summary['decided_by_rules']}")
    print(f"Wrongly hidden: {len(hidden)}  |  Fallbacks: {summary['fallbacks']}  |  "
          f"Per LLM call: {summary['avg_input_tokens']} input tokens, {summary['avg_latency_s']}s")
    for r in wrong:
        flag = "  <- WRONGLY HIDDEN" if r in hidden else ""
        print(f"  {r['subject'][:45]:45} | got {r['predicted']} ({r['source']}), expected {r['correct_type']}{flag}")

    # ---- 5. Log the run. "a" = append: add to the end of the file, keeping earlier runs ----
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(summary) + "\n")
    return summary