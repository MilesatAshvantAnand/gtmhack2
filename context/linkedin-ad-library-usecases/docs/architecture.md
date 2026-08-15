# Architecture — Foundation, Toolkit, Skills

This doc defines the layered architecture that every sub-project of this repo consumes.

**Read this doc before starting any new sub-project or skill.** It tells you what layer to build in and what dependencies you can rely on.

> **Status note (2026-07-06):** the layer *philosophy* below still holds, but two details are out of date and superseded by the design spec
> [`superpowers/specs/2026-07-06-zena-competitor-skills-design.md`](superpowers/specs/2026-07-06-zena-competitor-skills-design.md) (read §14):
> 1. **Skills ship self-contained under `.claude/skills/<name>/`, not `projects/skill-*/`.** The `projects/*` paths and per-sub-project `src/` layout shown below are the original plan; the built skill lives at `.claude/skills/keyword-competitors/` with a vendored engine copy (via `scripts/vendor.py`).
> 2. **`core/` is fully built**, not TBD: `schema`, `client`, `signals`, `report_html`, and `zenabm` (interface + stub) all exist. `core/client` reads `ZENABM_TOKEN` (falling back to `LINKEDIN_ACCESS_TOKEN`). The "What sits in `core/` today" section at the bottom is historical.

---

## Layered model

```
┌────────────────────────────────────────────────────────────────┐
│  Layer 4 — Skills (user-facing markdown skills)                │
│    projects/skill-01-keyword-competitors/                       │
│    projects/skill-02-competitor-deep-dive/                      │
│    (…future skills)                                             │
└────────────────────────────────────────────────────────────────┘
                            ▲ imports
┌────────────────────────────────────────────────────────────────┐
│  Layer 3 — Sub-project code (specialized workflows)            │
│    projects/01-b2b-outreach/  (paused, existing London work)   │
│    projects/skill-01-*/src/                                     │
│    projects/skill-02-*/src/                                     │
└────────────────────────────────────────────────────────────────┘
                            ▲ imports
┌────────────────────────────────────────────────────────────────┐
│  Layer 2 — Shared toolkit (core/)                              │
│    core/schema.py    — pydantic response models                 │
│    core/signals.py   — inferable-signals implementations        │
│    core/client.py    — LinkedIn API client wrapper              │
│    core/zenabm.py    — ZenABM MCP client (for skills 1 & 2)    │
└────────────────────────────────────────────────────────────────┘
                            ▲ derived from
┌────────────────────────────────────────────────────────────────┐
│  Layer 1 — Foundation (docs/api-knowledge-base/)               │
│    endpoints.md, call-patterns.md, response-fields.md,          │
│    inferable-signals.md, constraints.md, fixtures/, schema/     │
└────────────────────────────────────────────────────────────────┘
```

---

## Rules for what goes in each layer

### Layer 1 — Foundation (`docs/api-knowledge-base/`)

**Contents:** everything that describes what the LinkedIn Ad Library API returns, its constraints, and every inference we can safely derive. Plus raw response fixtures for regression.

**Rules:**
- No code. Prose + JSON fixtures + generated schemas only.
- Every claim must trace to a fixture.
- Update via re-running probe scripts + regenerating docs, not by hand-editing.

**Owned by:** the audit process. Any code depending on this should have a pytest regression against the fixtures.

### Layer 2 — Shared toolkit (`core/`)

**Contents:** code that any sub-project or skill can import. Framework-agnostic.

**Modules:**

| Module | Purpose | Depends on |
|---|---|---|
| `core.schema` | Pydantic models mirroring the API response envelope | Layer 1 (fixtures for validation) |
| `core.signals` | Every derivation from `inferable-signals.md` as a Python function | `core.schema` |
| `core.client` | LinkedIn API client (headers, retry, pagination). Wraps `requests`. | `core.schema` |
| `core.zenabm` | ZenABM MCP client wrapper (for skills 1 & 2) — fetches user's own ad performance data | (external MCP endpoint) |

**Rules:**
- No skill-specific logic. If it's only useful for one skill, it lives in that skill's directory.
- No I/O beyond the API clients (`core.client`, `core.zenabm`). No filesystem, no DB, no logging init.
- Type-hinted throughout. Pydantic models for every API boundary.
- Testable in isolation — no ZenABM tokens required for `core.schema` / `core.signals` tests.

**Anti-rule (rejected patterns):**
- ❌ CLI entry points in `core/` — belong in Layer 3 (sub-project) or Layer 4 (skill).
- ❌ Config files in `core/` — read `.env` at Layer 3.
- ❌ Business logic. `core.signals` returns numbers; interpretation belongs in the skill.

### Layer 3 — Sub-project code (`projects/*/src/`)

**Contents:** specialized workflow for one particular use case. Batch pipeline for London outreach. The Python glue behind a specific skill.

**Structure per sub-project:**
```
projects/skill-01-keyword-competitors/
├── PRD.md              # what this skill does + why + success criteria
├── plan.md             # implementation plan (steps + checkpoints)
├── SKILL.md            # the actual user-facing skill (Layer 4 artifact)
├── src/
│   ├── __init__.py
│   ├── discover.py     # keyword→competitor discovery
│   ├── compare.py      # side-by-side with ZenABM data
│   └── report.py       # format output
├── tests/
└── examples/
```

**Rules:**
- Every sub-project has its own PRD.md and plan.md before code is written.
- Reuse from `core/` liberally. Copy-paste from other sub-projects is a smell — extract to `core/`.

### Layer 4 — Skills (`projects/skill-*/SKILL.md`)

**Contents:** the user-facing markdown file (per anthropics/skills format) that ships to Claude Code users. Thin — orchestrates Layer 3 code + guides the user through onboarding.

**Rules:**
- Follows `anthropics/skills` schema exactly: YAML frontmatter + prose.
- Walks the user from cold start (never used the skill before) to result.
- Handles the ZenABM onboarding flow explicitly:
  1. Direct user to ZenABM signup URL if they don't have an account
  2. Explain LinkedIn connection inside ZenABM
  3. Explain ZenABM MCP installation
  4. Fetch LinkedIn API token
  5. Then run the actual analysis
- Bundles or references only what the skill actually needs from `core/`.

---

## How to add a new skill (checklist)

1. **Brainstorm** (superpowers:brainstorming) — clarify user intent, edge cases, success criteria
2. **Create `projects/skill-NN-<slug>/` directory**
3. **Write `PRD.md`** — problem, users, scope, non-goals, success criteria, milestones
4. **Write `plan.md`** — step-by-step implementation with review checkpoints (superpowers:writing-plans)
5. **Implement in `src/`** — TDD, one component at a time. Import from `core/` for shared logic. If you find yourself writing something a *second* skill will need, extract to `core/` immediately.
6. **Write `SKILL.md`** — the shippable markdown skill
7. **Test** — pytest for `src/` code; manual walkthrough for `SKILL.md`
8. **Review** — code-review skill + adversarial pass
9. **Publish** — copy to your public skills repo or into a plugin package

## What sits in `core/` today

- ✅ `core/schema.py` — pydantic response models with regression tests
- ⏳ `core/signals.py` — TBD, will implement each derivation from inferable-signals.md as a pure function
- ⏳ `core/client.py` — TBD, extract from `src/services/linkedin_client.py`
- ⏳ `core/zenabm.py` — TBD, wraps ZenABM MCP for skills 1 & 2

The `src/services/linkedin_client.py` in the repo root today is legacy from the b2b-outreach sub-project. First skill work should port what it needs into `core/client.py` with the bugs found by the audit fixed (countries param removed, adType param removed, etc.).

## Signal-tier compatibility rule (critical)

Every consumer of `core/signals` must respect the tier N/S/T system documented in `inferable-signals.md`:

- **Tier N** signals work for 100% of ads.
- **Tier S** signals require `details.adStatistics` — only ~55% of ads qualify. Skills MUST check `impression_data_coverage` before treating a Tier S signal's value as "signal false" vs "signal unknown".
- **Tier T** signals require non-empty `details.adTargeting` — same subset as Tier S. Same rule.

**Skill authors: if your skill silently reports "not advertising" when `coverage == none`, you're lying to the user.** Report "unknown for this advertiser" instead. This is the single most common signal-integrity failure mode.
