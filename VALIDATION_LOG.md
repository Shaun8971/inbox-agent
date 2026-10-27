# Validation log

| Date | Change | Accuracy | LLM only | Wrongly hidden | Fallbacks | Input tokens / call |
|---|---|---|---|---|---|---|
| 2026-10-26 | First review, LLM only (39 scored) | 100% | 100% | 0 | 1 | 4 (misreported) |
| 2026-10-26 | Baseline: token fix, JSON fix, calendar rules, optional_opportunity | __% | __/__ | __ | __ | __ |

## Findings
- Token count was a caching artifact: input is split into three usage fields; the real figure is their sum
- One reply failed JSON parsing; the checker now extracts the outermost { } block
- Review surfaced two taxonomy gaps: calendar replies (now rules) and optional leadership roles (new type)