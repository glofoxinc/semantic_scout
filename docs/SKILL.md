---
name: semantic-scout
description: "Universal Semantic Scout v5: any Jira ticket vs git branch, bot-ahead, no static bundles or Paginate."
metadata:
  schema_version: "5.0-scout-mcp"
---

# Semantic Scout v5 (universal)

**Input:** Jira summary + description + comments (Atlassian MCP) + product repo git diff.  
**Not used:** static ticket JSON, Paginate Forge, prebuilt country bundles.

## Setup

Clone **glofoxinc/semantic_scout** → **Setup Semantic Scout** → `scout_engine_health` passes.

## Primary call

`scout_ticket_review` on **gf-insights-fitnessbi** (or any repo):

- `ticket_key`, `summary`, `description`, `comments_text`
- `base_ref` = PR base branch
- `artifact_glob` only if Jira does not name the file (else inferred from title/text)
- `scope_mode` = `ticket` (default) | `strict`

Use response `review` + `deliverable_globs` + `bot_resolution_markdown`. Finish the **SCOUT RATING CARD** before PR **B**.

## Deliverable inference (automatic)

| Jira mentions | Inferred glob |
|---------------|----------------|
| `Report Name (paginated)` | `**/Report Name.rdl` |
| `Name (dashboard)` | `**/*Name*.Report/**/report.json` |
| semantic model / `.tmdl` | `**/*.SemanticModel/**/*.tmdl` |
| explicit `Something.rdl` in text | `**/Something.rdl` |

Specialized RDL checks (e.g. country filter) run **only** when that AC text maps to a check id — not for every ticket.
