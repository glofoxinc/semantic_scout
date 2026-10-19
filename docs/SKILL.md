---
name: semantic-scout
description: "Semantic Scout MCP: before PR, call scout_ticket_review and show review_card_markdown. Setup Semantic Scout once."
---

# Semantic Scout (MCP-first)

**Do not guess the review.** For every **Semantic Scout for AN-XXXX** request:

1. Fetch Jira (summary, description, comments) via Atlassian MCP.
2. Call **`scout_ticket_review`** on the product repo (`repo_root`, `base_ref`, full Jira text).
3. Show the user **`review_card_markdown`** from the response (verbatim).
4. State **`readiness`** (`READY` / `NOT READY`) and **`confidence`** from the same response.
5. Open a PR only when readiness is **READY** (user may override with explicit risk acceptance).

**Setup (once):** **Setup Semantic Scout** → `scout_engine_health` must pass.

**Daily:** **Semantic Scout for AN-XXXX**

Team guide: https://glofoxinc.github.io/semantic_scout/DOCUMENTATION.html
