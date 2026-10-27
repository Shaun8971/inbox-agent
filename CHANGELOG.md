# Change log

## 2026-10-26
- Phase 2: taxonomy and config file; rules for newsletters, Canvas, calendar replies; LLM classifier with injection defenses and reply checking; frozen answer key and eval with run history
- Fixed: token counting ignored cache fields (4 → 1,420 per email); JSON parsing failed on text around the reply
- Added after review: calendar_accepted / calendar_declined rules; optional_opportunity type

## 2026-10-24
- Phase 1: Gmail sign-in (Internal app, read-only scope); fetch unread emails with full bodies; header signals (To, Cc, mass mail)

## 2026-10-23
- Phase 0: project setup, secrets controls, LLM gateway test (~3 hrs)