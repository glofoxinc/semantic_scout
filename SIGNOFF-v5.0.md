# Semantic Scout v5.0 — Product sign-off

**Date:** 2026-10-18  
**Canonical repo:** [glofoxinc/semantic_scout](https://github.com/glofoxinc/semantic_scout)  
**Version:** MCP `SCOUT_VERSION` **5.0.0** · skill schema **5.0-scout-mcp**  
**Sign-off owner:** Lakshmi Narasimha Naidu Yalamarti (CC171 Insights & Reporting)

---

## Scope of this sign-off

This certifies the **public thin skill + MCP** release is complete for team rollout. It does **not** claim Scout replaces human QA, PBRS, or the **SCOUT RATING CARD / B** gate before PR.

---

## Deliverables — VERIFIED

| Item | Evidence |
|------|----------|
| Universal engine (Jira + git only) | No Paginate bridge; no runtime load of `data/examples/ticket_profiles/` |
| Primary MCP tool | `scout_ticket_review` → structured `review` + `deliverable_globs` + `bot_resolution_markdown` |
| Deliverable inference | `infer_deliverable_globs()` for `.rdl`, dashboard `.Report`, `.tmdl`, explicit filenames |
| Ticket-scoped RDL checks | Country/doc/filter checks only when requirement text warrants |
| Git scope | `scope_mode=ticket` — extra branch files → info, not false delivery=0 |
| Bot ahead | Predictions excluded from delivery score; `ready_bot_clear` separate |
| Engine sign-off | `python -m lib.signoff_gate` — 4/4 PASS |
| Automated tests | `pytest scout/tests` — 4 passed |
| Team guide | `DOCUMENTATION.html` aligned to v5 |
| Setup skill | `Setup Semantic Scout` → `docs/SKILL.md` + `scout/mcp/server.py` |
| CI | `.github/workflows/ci.yml` on `main` |
| GitHub Pages | `pages.yml` publishes `DOCUMENTATION.html` |

---

## Operator checklist (each machine — one time)

1. Clone or pull **glofoxinc/semantic_scout** `main`.
2. In Cursor: **Setup Semantic Scout** (installs skill + MCP snippet).
3. `pip install -r scout/requirements.txt`
4. MCP: **`scout_engine_health`** returns OK.
5. Dry run: **Semantic Scout for** a real **AN-XXXX** on the product clone with full Jira text.

---

## Known limits (explicit — not defects)

| Limit | Mitigation |
|-------|------------|
| Dashboard / TMDL AC | Mostly keyword + diff heuristics; deep visual parity is manual |
| PBRS / PDF layout | Out of Scout; validate in Service |
| Odd RDL layouts | Regex heuristics may need human override |
| Bot corpus | Historical PR patterns — advisory only |
| Internal `semantic-scout` dev tree | **Not** canonical; R&D/corpus only — use public repo for runtime |

---

## Release gate result

```
PRODUCT: Semantic Scout v5.0
ENGINE SIGN-OFF: PASS (4/4)
PYTEST: PASS (4/4)
DOCS + CI: SHIPPED
READY FOR TEAM ROLLOUT: YES
HUMAN PR GATE (A/B/C + RATING CARD): STILL REQUIRED
```

**Signed:** Product sign-off for v5.0 public release — engine, MCP contract, docs, and CI complete. Per-ticket **READY** remains the analyst’s call after the rating card.
