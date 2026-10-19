# Semantic Scout

**Before you open a PR:** rate Jira requirements vs your branch, list missings, and get ahead suggestions (docs, dashboard companions, bot comments).

| Resource | Link |
|----------|------|
| Team guide (browser) | https://glofoxinc.github.io/semantic_scout/DOCUMENTATION.html — Goal, success criteria, Scout vs KPI Forge |
| Cursor skill (install source) | [`docs/SKILL.md`](./docs/SKILL.md) |
| Hero image | [`share-image.svg`](./share-image.svg) |

## What you clone (small surface)

| Path | Who touches it |
|------|----------------|
| `docs/SKILL.md` | Users — one skill file after setup |
| `scout/mcp/server.py` | Cursor MCP (auto-wired on setup) |
| `scout/lib/` | Engine only — do not edit for daily work |
| `DOCUMENTATION.html` | Reference / onboarding deck |

Same team pattern as [KPI Forge](https://github.com/glofoxinc/kpi-forge): **Cursor MCP** — say **Setup Semantic Scout**, then **Semantic Scout for AN-XXXX** before each PR.

## Setup (once, ~5 minutes)

In Cursor, say **Setup Semantic Scout**. Answer GitHub/Jira once if asked.

Then: **Semantic Scout for AN-XXXX** on your feature branch.

## Rollout plan (team / maintainers)

1. **Public repo** (`semantic_scout`) — ship `docs/SKILL.md` + `scout/` MCP; keep full corpus and ticket R&D in internal dev repo.
2. **Setup** — agent copies skill, merges `scout/config/cursor-mcp.example.json`, runs `scout_engine_health`.
3. **Daily** — Jira (Atlassian MCP) + git diff + `scout_requirement_matrix` + `scout_gap_report` on the product clone.
4. **Paginated tickets** — Scout scores **delivery vs Jira** from git; use Paginate Forge separately only when building or patching RDL.
5. **Slack** — post intros via Slack MCP (`/invite @Cursor` in private channels); see team formatting rules.
6. **Internal dev** — `projects/stable/semantic-scout` is R&D/corpus only; **semantic_scout** on GitHub is the runtime source of truth.
7. **Sign-off** — see [`SIGNOFF-v5.0.md`](./SIGNOFF-v5.0.md) after each major release.

Maintainers: engine lives under `scout/`; see `mcp.json.example` for local wiring.
