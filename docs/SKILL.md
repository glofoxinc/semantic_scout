---
name: semantic-scout
description: "Semantic Scout only: Jira requirements vs branch, git scope, bot-ahead, ratings before PR. Use Semantic Scout, rate this ticket, before PR, bot ahead, Setup Semantic Scout."
metadata:
  team: CC171 Insights & Reporting / Glofox Analytics
  schema_version: "4.2-scout-mcp"
  surfaces: [ide, mcp]
---

# Semantic Scout

**Scout is independent.** Jira (Atlassian MCP) + product repo (git) + **semantic-scout** MCP. No Paginate Forge step.

## User

1. Clone **glofoxinc/semantic_scout** → open in Cursor.
2. **Setup Semantic Scout**
3. **Semantic Scout for AN-XXXX** on the **product repo** path (e.g. gf-insights-fitnessbi), not only the scout clone.

## Setup (agent)

1. `docs/SKILL.md` → `%USERPROFILE%\.cursor\skills\semantic-scout\SKILL.md`
2. Wire `scout/mcp/server.py` via `scout/config/cursor-mcp.example.json`
3. Atlassian + GitHub MCP; `pip install -r scout/requirements.txt`; `scout_engine_health` must pass

## Daily run — prefer one MCP call

**`scout_ticket_review`** with:

- `repo_root` = product clone
- Full Jira: `summary`, `description`, `comments_text`
- `base_ref` = PR base (`origin/main` or `origin/Standard_dev`)
- Optional: `head_sha`, `circuit_reviewed_sha` (stale Circuit bot detection)

Then **read files** and finalize the card. MCP output is not sign-off.

### Flow

1. Jira fetch (Atlassian).
2. `scout_ticket_review` → matrix markdown, scope report, bot-ahead, gap ratings.
3. For each matrix row: open cited `.rdl` / `report.json` if status is not honestly `met`.
4. **SCOUT RATING CARD** + A/B/C.

### Hard rules

- `unverified` = not done for READY.
- Scope: diff paths must match Jira `in_scope` (MCP flags extras).
- Bot-ahead: fix or reply **before** PR when severity is gap/blocker.
- No PR until **B**.

## SCOUT RATING CARD

```
═══════════════════════════════════════════
SCOUT RATING CARD — {TICKET}
═══════════════════════════════════════════
Repo @ branch (base: {base_ref})

Jira clarity / Delivery / Combined: from scout_ticket_review (override if wrong)
READY: YES only if you verified every must-have AC

Scope: {from scope_report}
Bot ahead: {top 3 from bot_ahead_markdown — fixed or planned}

Matrix: {REQ} {status} — {path evidence}

Missings / Ahead / A B C
═══════════════════════════════════════════
```

## MCP tools

| Tool | Use |
|------|-----|
| `scout_engine_health` | After install |
| `scout_ticket_review` | **Primary** — matrix + git scope + requirements + bot |
| `scout_branch_diff` | Changed paths only |
| `scout_bot_ahead` | Bot predictions from path list + diff |
| `scout_requirement_matrix` | Matrix only |
| `scout_route_repository` | AN/PIC → repo |

## Country tickets (AN-5603–5606)

Scout checks are **tied to AC ids** (`country_filter`, `country_column_first`, `default_all_countries`, `doc_country_filter`). It does not run country/doc rules on unrelated tickets.

## Limits

- Regex/heuristics can be wrong — **you** override in the card.
- Bot corpus is historical — still run human PBRS when AC needs visual proof.
- Dashboard / `.tmdl` tickets need matrix bullets that name those artifacts.
