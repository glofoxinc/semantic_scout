---
name: semantic-scout
description: "Semantic Scout v4.3: Jira vs branch, git scope, bot resolution checklist, per-requirement evidence. Setup Semantic Scout; Semantic Scout for AN-XXXX."
metadata:
  schema_version: "4.3-scout-mcp"
---

# Semantic Scout v4.3

**Independent.** `scout_ticket_review` on the **product repo** is the primary call.

## Setup

1. Clone **glofoxinc/semantic_scout** → **Setup Semantic Scout** (agent installs `docs/SKILL.md` + MCP).
2. `scout_engine_health` must pass (5 engine checks including country column RDL).

## Daily

```
scout_ticket_review(
  repo_root = <gf-insights-fitnessbi>,
  ticket_key, summary, description, comments_text,
  base_ref = origin/main | origin/Standard_dev,
  head_sha, circuit_reviewed_sha,   // optional Circuit stale bot
  scope_mode = ticket | strict      // ticket = warn on other reports on branch
)
```

Use JSON field **`review`** for ratings, requirements, **`bot_resolution_markdown`**, and **`human_gate`**.

**You** must open each file and confirm `met` rows before **B**.

## Scope modes

| Mode | Behavior |
|------|----------|
| `ticket` (default) | Other BI files on branch → **info** (split PR reminder), not delivery=0 |
| `strict` | Any out-of-scope path → **blocker** |

## No Paginate Forge

Standards line stays **n/a**. Optional legacy audit only via internal flag (not in default MCP).
