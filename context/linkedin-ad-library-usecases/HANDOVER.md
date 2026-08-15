# HANDOVER - LinkedIn Ad Library Use-Cases (Zena skills)

> Clean **exit-now / resume-later** brief. Updated 2026-07-12.
> Read this first, then [`CLAUDE.md`](CLAUDE.md) (directives + current state) and the current design spec
> [`docs/superpowers/specs/2026-07-12-abm-competitor-intel-design.md`](docs/superpowers/specs/2026-07-12-abm-competitor-intel-design.md)
> and plan [`docs/superpowers/plans/2026-07-12-abm-competitor-intel.md`](docs/superpowers/plans/2026-07-12-abm-competitor-intel.md).

---

## 0. What changed since the last handover (2026-07-06)

The skill was renamed and fundamentally rearchitected (spec + plan under `docs/superpowers/` `2026-07-12-abm-competitor-intel-*`):

- **Renamed:** `keyword-competitors` -> `abm-competitor-intel` at `.claude/skills/abm-competitor-intel/`.
- **ZenABM API:** the skill now runs entirely on the deployed ZenABM API (`https://app.zenabm.com/api/v1`) via one Bearer token from `https://app.zenabm.com/api-keys`. No direct LinkedIn calls; no MCP; no client-side caps (all limits and plan-gating are server-side).
- **Competitor-first:** the user pastes competitor LinkedIn URLs or names. Keyword search is kept as a flagged-approximate discovery helper only.
- **You-vs-them comparison:** new `core/comparison.py` produces a head-to-head panel (activity/format/share-of-voice, scale vs. efficiency, concrete recommended moves).
- **Engine rebuilt:** `core/zenabm_api.py` (client), `core/zenabm_models.py` (Pydantic v2), `core/signals.py` (adapted), `core/comparison.py`, `core/report_html.py` (ZenABM-branded renderer). Entry: `scripts/competitor_scan.py`.
- **Retired:** cumulative-cap ledger (`session_ledger.py`), `ZENA_DEV` flag, pasted LinkedIn token, forbidden-params guard, and MCP-hybrid approach.
- **3-step onboarding:** sign up at `app.zenabm.com/signup` -> connect LinkedIn in ZenABM -> copy the api-keys token. No placeholders; the URLs are live.
- Suite: **385 scoped tests green** (was 197 before the rebuild).

---

## 1. Final state (one paragraph)

The **foundation** (fixture-backed API knowledge base + 114-test regression) and the **`core/` engine toolkit** (`zenabm_api`, `zenabm_models`, `signals`, `comparison`, `report_html`) are built and tested. The **current shareable skill, `.claude/skills/abm-competitor-intel/`** (persona "Zena by ZenABM"), is **built, self-contained, reviewed, and live-validated end-to-end**. It profiles competitors' LinkedIn ads via the deployed ZenABM API and produces a **you-vs-them head-to-head comparison** in one ZenABM-branded, self-contained, downloadable HTML report with Zena-authored insights. Full scoped suite: **385 tests green**. The skill is destined for `ZENABM/linkedin-abm-skills` (org plugin monorepo); this workshop repo is where it is developed.

---

## 2. What's done

### Layer 1 - Foundation `docs/api-knowledge-base/` - DONE
Single source of truth for the raw LinkedIn Ad Library API. `endpoints.md`, `call-patterns.md`, `response-fields.md`, `inferable-signals.md` (every derived signal with formula + tier N/S/T + corpus validation), `constraints.md`, **118 real fixtures**, JSON schemas, and the `tests/knowledge_base/` regression (**114 tests**). If LinkedIn changes their schema, these fail first.

### Layer 2 - Engine `core/` - DONE
| Module | Notes |
|---|---|
| `core/zenabm_api.py` | ZenABM API client. Reads **`ZENABM_TOKEN`** from env. Handles auth, retry, pagination. Raises `ZenABMAuthError`/`ZenABMPlanError` for graceful upsell. |
| `core/zenabm_models.py` | Pydantic v2 models for the ZenABM API responses. |
| `core/signals.py` | Tier-aware signal functions adapted to `zenabm_models`. Golden rule enforced (Tier S/T -> unknown, never "no", when coverage is none). |
| `core/comparison.py` | You-vs-them: head-to-head activity/format/share-of-voice, scale vs. efficiency, recommended moves. |
| `core/report_html.py` | Self-contained ZenABM-branded HTML renderer (stdlib-only; Artifact-CSP-safe). Lean by default, expandable ABM detail. Download-PDF button. |
| `core/client.py` | Legacy raw-LinkedIn client (CTO-brief reference; kept, do not delete or wire in). |
| `core/schema.py` | Legacy raw-LinkedIn Pydantic models (same). |

(`report_data.json`, `report.html`, `sample-*.html`, `sample_report_data.py` under `core/` are working artifacts, not shipped code.)

### Layer 3/4 - Skill `.claude/skills/abm-competitor-intel/` - BUILT, REVIEWED, LIVE-VALIDATED
- `SKILL.md` - Zena persona + the full guided conversation (onboarding -> competitors -> scan -> author insights -> deliver).
- `scripts/competitor_scan.py` - the skill entry: calls the ZenABM API for each competitor, derives signals, runs comparison, writes `report_data.json` + a compact DIGEST, renders a draft, and (`--render`) bakes Zena's authored insights into the final `report.html`.
- `scripts/core/` - **vendored copy** of the engine (via `scripts/vendor.py`) so the skill ships standalone.
- `references/onboarding.md`, `examples/`, `tests/test_competitor_scan.py` (50 tests) + `tests/test_skill_md.py` (36 tests).

### Distribution - DONE
Self-contained skill folder. Install via Claude Code (drop into `.claude/skills/` or `~/.claude/skills/`), or via Cowork (zip the `abm-competitor-intel` folder and upload). Repo also has `.claude/.claude-plugin/plugin.json` for marketplace/plugin install. Destined for org plugin monorepo `ZENABM/linkedin-abm-skills` via PR + release zip.

---

## 3. What's left (to pick up)

1. **Contribute to `ZENABM/linkedin-abm-skills`** - the org plugin monorepo. Open a PR with the `abm-competitor-intel` skill folder + a release zip. Follow the monorepo's contribution guidelines.
2. **Run the keyword-precision probe live** (still open from before): `scripts/probe_keyword_precision.py` needs a valid token. Run it and record the conclusion (whether the keyword param has precision operators or not).
3. **Optional:** further skill-reviewer pass on the description for auto-trigger precision on the new competitor-first framing.

---

## 4. How to install + test the skill

**Test (offline, no token):**
```bash
cd /Users/bilal.ahmad/CC/linkedin-ad-library-usecases
source .venv/bin/activate        # a .venv with pydantic+pytest+requests+python-dotenv exists
python -m pytest tests/knowledge_base tests/test_zenabm_api.py tests/test_zenabm_models.py \
  tests/test_signals_zenabm.py tests/test_comparison.py tests/test_report_html.py \
  .claude/skills/abm-competitor-intel/tests -q
# expect: 385 passed
```

Note: `tests/test_agent.py`, `tests/test_infrastructure.py`, `tests/test_tool_implementations.py` have pre-existing legacy failures (ModuleNotFoundError for the paused Streamlit + batch sub-projects). Do not include in the canonical run.

**Install the skill:**
- Claude Code: copy the `abm-competitor-intel` folder into `.claude/skills/` (project) or `~/.claude/skills/` (global).
- Cowork: `cd .claude/skills && zip -r abm-competitor-intel.zip abm-competitor-intel` and upload the zip.

**Run it (as a user would):** trigger it in chat (e.g. "show me my competitors' LinkedIn ads"); Zena walks setup and produces the report. To run the engine directly for a smoke test:
```bash
ZENABM_TOKEN="<token>" python3 .claude/skills/abm-competitor-intel/scripts/competitor_scan.py \
  --competitors "Personio, HiBob" --out-dir /tmp/zena-run
```

**After changing any `core/` engine module:** re-vendor so the skill's copy stays in sync:
```bash
python3 scripts/vendor.py
```

---

## 5. Gotcha - the `uv` Stop-hook

If a session in this repo shows a **Stop-hook failure mentioning `uv`**, it comes from the **data-engineering plugin** (an Airflow/Astronomer plugin whose Stop hook shells out to `uv`, which isn't installed on this machine). It does not affect this repo's work. Fix either way:
- `brew install uv`, or
- disable/remove the data-engineering plugin.

(Note: `.claude/settings.local.json` currently has `"skillOverrides": {}` - the skill is not suppressed. Set `"abm-competitor-intel": "off"` if you want to avoid auto-triggering during doc/dev work in this repo.)

---

## 6. Where to pick up

Highest-leverage on-roadmap path:
1. **Contribute to org monorepo** (§3.1) - the main outstanding distribution step.
2. **Run the keyword-precision probe live** (§3.2) - small, closes a long-open item.
3. **Optionally** re-run skill-reviewer on the updated description.

---

## 7. Paused / legacy (do not resume unless asked)

- **B2B outreach batch pipeline** - root-level scripts (`batch_lookup.py`, `db.py`, `enrich_ads.py`, `import_contacts.py`, `export.py`, `rematch_contacts.py`, `prepare_london_run.py`). Standalone SQLite pipeline. The legacy `src/services/linkedin_client.py` has the `countries`/`adType` bugs (always 400) - port fixes into `core/zenabm_api.py` if ever revived.
- **Streamlit chat agent** - `app.py` + `src/agent/`, `src/tools/`, `src/ui/`. Never run end-to-end; DB schema incompatible with the batch pipeline's. Docs `docs/TOOL_REFERENCE.md` + `docs/USAGE_EXAMPLES.md` are labeled legacy. `docs/LINKEDIN_API_OFFICIAL.md` carries a SUPERSEDED banner pointing to `docs/api-knowledge-base/`.
- **Legacy raw-LinkedIn engine** - `core/client.py`, `core/schema.py`, `tests/test_core_client.py`. Kept as the CTO-brief reference implementation. Do not delete.
- **Old `keyword-competitors` skill** - retired; replaced by `abm-competitor-intel`. Historical specs/plans for the keyword-competitors hardening remain under `docs/superpowers/` as dated records.
