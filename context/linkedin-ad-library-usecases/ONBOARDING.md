# ONBOARDING - LinkedIn Ad Library + Zena Skills

> You're picking up this project. This is the one doc to read first. It gets you productive fast, then points you to the deeper references. Updated 2026-07-12.

## 1. What this project is (one paragraph)

Two things stacked. **(1) A fixture-backed knowledge base** of the LinkedIn Ad Library API - a validated audit of exactly what the API returns, what it *can't* do, and what you can validly *infer* from it. **(2) A platform for building shareable Claude Skills** - branded **Zena by ZenABM** - on top of that foundation. The current skill, **`abm-competitor-intel`**, is built and live-validated: a user pastes competitor LinkedIn URLs or names and Zena produces a you-vs-them competitive-intelligence report showing who is advertising what and how the user's own ads stack up - all powered by the deployed ZenABM API. The north star: *never re-audit the API - look facts up in the knowledge base, build skills on top.*

## 2. Get up to speed in 5 minutes

```bash
git clone https://github.com/bilalahmad20/linkedin-ad-library-usecases.git
cd linkedin-ad-library-usecases
python3 -m venv .venv && source .venv/bin/activate
pip install requests pydantic python-dotenv pytest

# Confirm foundation + engine + skill are all intact (offline, no token, no network):
python -m pytest tests/knowledge_base tests/test_zenabm_api.py tests/test_zenabm_models.py \
  tests/test_signals_zenabm.py tests/test_comparison.py tests/test_report_html.py \
  .claude/skills/abm-competitor-intel/tests -q
# expect: 385 passed
```

If that's green, everything works. The whole suite runs offline against cached fixtures.

Note: `tests/test_agent.py`, `tests/test_infrastructure.py`, and `tests/test_tool_implementations.py` have pre-existing ModuleNotFoundError failures from the paused Streamlit + batch sub-projects - exclude them from the canonical run above.

## 3. Architecture - the 4 layers

```
Layer 4  Skill (persona + conversation)   .claude/skills/abm-competitor-intel/SKILL.md
Layer 3  Skill entry (the runnable)       .claude/skills/abm-competitor-intel/scripts/competitor_scan.py
Layer 2  Shared engine toolkit            core/  (zenabm_api, zenabm_models, signals, comparison, report_html)
Layer 1  Foundation (truth + regression)  docs/api-knowledge-base/  (docs + 118 fixtures + JSON schema)
```

Knowledge (Layer 1) is the source of truth; code (Layer 2) implements it; the skill (Layers 3-4) composes it. Every code file's docstring points *back* to the markdown spec it implements. If LinkedIn changes their schema, the Layer 1 regression fails first.

The CTO built a ZenABM API wrapper over the raw LinkedIn Ad Library API (`docs/ad-library-api-for-zenabm-wrapper.md` is the brief that informed it). The skill calls that wrapper, not LinkedIn directly.

## 4. The built skill - `abm-competitor-intel`

- **What it does:** the user pastes competitor LinkedIn URLs or names; Zena profiles each competitor's LinkedIn ad activity via the ZenABM API, then produces a **you-vs-them** head-to-head comparison (activity, format mix, share-of-voice, scale vs. efficiency, concrete recommended moves). Deliverable: one ZenABM-branded, self-contained, downloadable HTML report.
- **Agent-driven:** the user only chats. The agent runs the bundled Python behind the scenes.
- **Two-step insight authoring:** `competitor_scan.py` computes signals -> writes `report_data.json` + a DIGEST -> **Zena authors the insights** back into the JSON -> `--render` bakes them into `report.html`.
- **API and auth:** runs entirely on the deployed ZenABM API (`https://app.zenabm.com/api/v1`). One Bearer token, obtained at `https://app.zenabm.com/api-keys`. No direct LinkedIn calls; no MCP; no client-side caps - all limits and plan-gating are server-side. The skill degrades gracefully on trial or expiry (warm upsell, no hard-cap language).
- **Distribution:** see [`.claude/skills/abm-competitor-intel/DISTRIBUTION.md`](.claude/skills/abm-competitor-intel/DISTRIBUTION.md) for how to share/install it in Claude Code, Cowork, and other agents. The skill is destined for the org plugin monorepo `ZENABM/linkedin-abm-skills`.

## 5. Where everything lives

| Path | What it is |
|---|---|
| `docs/api-knowledge-base/` | **The foundation.** Read `README.md` first; `call-patterns.md`, `constraints.md`, `response-fields.md`, `inferable-signals.md`; 118 fixtures |
| `docs/ad-library-api-for-zenabm-wrapper.md` | CTO brief that informed the deployed ZenABM API wrapper |
| `core/zenabm_api.py` | ZenABM API client (Bearer token, retry, pagination, graceful error handling) |
| `core/zenabm_models.py` | Pydantic v2 models for the ZenABM API responses |
| `core/signals.py` | Tier-aware signal derivations (the golden rule lives here; adapted to zenabm_models) |
| `core/comparison.py` | You-vs-them: head-to-head activity/format/share-of-voice + scale vs. efficiency |
| `core/report_html.py` | Self-contained ZenABM-branded HTML renderer (stdlib-only) |
| `core/client.py` | Legacy raw-LinkedIn client (CTO-brief reference; kept, do not wire in) |
| `.claude/skills/abm-competitor-intel/SKILL.md` | Zena persona + the full guided conversation |
| `.claude/skills/abm-competitor-intel/scripts/competitor_scan.py` | Skill entry (compute -> report_data.json -> render) |
| `.claude/skills/abm-competitor-intel/scripts/core/` | **Vendored** copy of `core/` so the skill ships standalone |
| `scripts/vendor.py` | Copies `core/` into each skill's `scripts/core/` |
| `CLAUDE.md` | Directives for Claude Code sessions in this repo (hard rules) |
| `HANDOVER.md` | The technical resume brief (read after this) |
| `docs/superpowers/specs/2026-07-12-abm-competitor-intel-design.md` | Current design spec |
| `docs/superpowers/plans/2026-07-12-abm-competitor-intel.md` | Current implementation plan |

## 6. The rules that matter (do not break)

- **The golden rule:** LinkedIn only exposes impression stats for EU/EEA-visible ads. For a US-only advertiser those stats are simply *absent* - so Tier S/T signals must return **UNKNOWN (`None`)**, never `False`. Never report "not advertising" from missing data. Enforced in `core/signals.py`.
- **Forbidden params (raw LinkedIn):** `countries` and `adType` always return HTTP 400. The legacy `core/client.py` has a `FORBIDDEN_PARAMS` guard; the ZenABM API wrapper handles this server-side.
- **Plan-gating:** no client-side caps in the current skill. `ZenABMAuthError`/`ZenABMPlanError` from `core/zenabm_api.py` trigger a warm upsell line and a graceful exit.
- Full list with worked examples: `docs/api-knowledge-base/constraints.md` and `CLAUDE.md`.

## 7. Current state and what's next

- **Foundation:** complete. **Skill `abm-competitor-intel`:** built, reviewed, live-validated. **385 scoped tests green.**
- **What's next (priority order):**
  1. **Contribute to `ZENABM/linkedin-abm-skills`** - open a PR with the skill folder + a release zip. Main outstanding distribution step.
  2. **Run the keyword-precision probe live** (`scripts/probe_keyword_precision.py`, needs a token) and record the conclusion.
  3. **Optional:** further skill-reviewer pass on the description for auto-trigger precision on the competitor-first framing.

## 8. Gotchas

- **Token:** one ZenABM Bearer token, obtained at `https://app.zenabm.com/api-keys`. Set as `ZENABM_TOKEN` in the environment (or in `.env`). Plan gating is server-side; a trial or expired token causes a graceful upsell, not a hard crash.
- **After changing any `core/` engine module:** run `python3 scripts/vendor.py` to re-sync the skill's vendored `scripts/core/`, then run the suite. (Skill-only files like `competitor_scan.py` are not vendored - edit them in place.)
- **Legacy tests excluded:** `tests/test_agent.py`, `tests/test_infrastructure.py`, `tests/test_tool_implementations.py` fail with ModuleNotFoundError (paused Streamlit + batch sub-projects). Do not include in the canonical run.
- **`uv` Stop-hook noise:** a Stop-hook failure mentioning `uv` comes from an unrelated data-engineering plugin, not this repo. `brew install uv` or disable that plugin. Harmless.
- **Legacy code (do not resume unless asked):** root-level `batch_lookup.py`, `db.py`, `app.py`, `src/` are a paused B2B pipeline + Streamlit agent. `src/services/linkedin_client.py` has the `countries`/`adType` bugs - use `core/zenabm_api.py`.

## 9. Go deeper

| Read when | Doc |
|---|---|
| Directives + hard rules for working in this repo | [`CLAUDE.md`](CLAUDE.md) |
| The technical resume brief (final state, what's left) | [`HANDOVER.md`](HANDOVER.md) |
| How to share/install the skill (Claude Code, Cowork, other agents) | [`.claude/skills/abm-competitor-intel/DISTRIBUTION.md`](.claude/skills/abm-competitor-intel/DISTRIBUTION.md) |
| Everything about the raw LinkedIn Ad Library API | [`docs/api-knowledge-base/README.md`](docs/api-knowledge-base/README.md) |
| CTO brief that informed the ZenABM API wrapper | [`docs/ad-library-api-for-zenabm-wrapper.md`](docs/ad-library-api-for-zenabm-wrapper.md) |
| Current design spec | [`docs/superpowers/specs/2026-07-12-abm-competitor-intel-design.md`](docs/superpowers/specs/2026-07-12-abm-competitor-intel-design.md) |
| Current implementation plan | [`docs/superpowers/plans/2026-07-12-abm-competitor-intel.md`](docs/superpowers/plans/2026-07-12-abm-competitor-intel.md) |
