# Semantic Scout

**Before you open a PR:** rate Jira requirements vs your branch, list missings, and get ahead suggestions (docs, dashboard companions, bot comments).

| Resource | Link |
|----------|------|
| Team guide (browser) | https://glofoxinc.github.io/semantic_scout/DOCUMENTATION.html |
| Cursor skill (install source) | [`docs/SKILL.md`](./docs/SKILL.md) |
| Hero image | [`share-image.svg`](./share-image.svg) |

## What you clone (small surface)

| Path | Who touches it |
|------|----------------|
| `docs/SKILL.md` | Users — one skill file after setup |
| `scout/mcp/server.py` | Cursor MCP (auto-wired on setup) |
| `scout/lib/` | Engine only — do not edit for daily work |
| `DOCUMENTATION.html` | Reference / onboarding deck |

Same pattern as [Semantic Forge](https://github.com/glofoxinc/semantic_forge): thin skill + MCP for heavy work.

## Setup (once, ~5 minutes)

In Cursor, with this repo open, say **Setup Semantic Scout**. The agent installs the skill and MCP; you only answer GitHub/Jira once if asked.

Then: **Semantic Scout for AN-XXXX** (your real ticket).

## Rollout plan (team / maintainers)

1. **Public repo** (`semantic_scout`) — ship `docs/SKILL.md` + `scout/` MCP; keep full corpus and ticket R&D in internal dev repo.
2. **Setup** — agent copies skill, merges `scout/config/cursor-mcp.example.json`, runs `scout_engine_health`.
3. **Daily** — Jira (Atlassian MCP) + git diff + `scout_requirement_matrix` + `scout_gap_report` on the product clone.
4. **Paginated tickets** — pair with Paginate Forge for standards; Scout scores **delivery** vs Jira separately.
5. **Slack** — post intros via Slack MCP (`/invite @Cursor` in private channels); see team formatting rules.
6. **Internal dev** — reconcile `semantic-scout` git history, commit libs/tests, regenerate public `scout/lib` on release tags only.

## MCP tools

- **`scout_ticket_review`** — primary: Jira + git scope + per-requirement ratings + bot-ahead  
- `scout_engine_health` — engine sign-off after install  
- `scout_branch_diff` / `scout_bot_ahead` — split steps  
- `scout_requirement_matrix` / `scout_route_repository` — helpers  

See `scout/config/cursor-mcp.example.json` and root `mcp.json.example`.
