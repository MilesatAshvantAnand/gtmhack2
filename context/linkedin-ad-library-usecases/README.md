# LinkedIn Ad Library - Knowledge Base + Zena Skills Platform

Private. A validated audit of the LinkedIn Ad Library API and a platform for building shareable Claude Skills on top of it.

**Foundation:** what the API returns, what it can't do, and what we can validly derive from it - all fixture-backed and pytest-regression-covered.
**On top of the foundation:** a `core/` engine toolkit and shareable, self-contained skills branded as **Zena by ZenABM**. The shipped skill, **`abm-competitor-intel`**, profiles competitors' LinkedIn ads and compares them to the user's own ads - live, against the deployed ZenABM API.

---

## Repo tour

```
docs/
├── api-knowledge-base/     THE FOUNDATION - read first
│   ├── README.md           Index of everything below
│   ├── call-patterns.md    "For every way to call the API, here's the response"
│   ├── constraints.md      Hard rules + real bugs discovered
│   ├── endpoints.md        Params, envelope, error shapes
│   ├── response-fields.md  Every field, type, coverage %, examples
│   ├── inferable-signals.md  Worked-example derivations, tier N/S/T rules
│   ├── schema/             Auto-generated JSON schemas
│   └── fixtures/           118 raw response JSONs (versioned truth)
├── ad-library-api-for-zenabm-wrapper.md
│                           CTO brief that informed the deployed ZenABM API wrapper
├── architecture.md         Layered model (layer philosophy; dir map superseded)
└── superpowers/
    ├── specs/2026-07-12-abm-competitor-intel-design.md   CURRENT design spec
    └── plans/2026-07-12-abm-competitor-intel.md          CURRENT implementation plan
    (older keyword-competitors hardening specs kept as dated records)

core/                        SHARED ENGINE (Layer 2) - single source of truth
├── zenabm_api.py            ZenABM API client (Bearer token, retry, pagination)
├── zenabm_models.py         Pydantic v2 models for the ZenABM API responses
├── signals.py               Tier-aware signal functions (adapted to ZenABM models)
├── comparison.py            You-vs-them: head-to-head activity/format/share-of-voice
├── report_html.py           Self-contained ZenABM-branded HTML renderer (stdlib-only)
├── client.py                Legacy raw-LinkedIn client (CTO-brief reference; kept as-is)
└── schema.py                Legacy raw-LinkedIn pydantic models (kept as-is)

.claude/
├── .claude-plugin/plugin.json   Enables Cowork / marketplace install
└── skills/
    └── abm-competitor-intel/    THE BUILT SKILL - self-contained, independently installable
        ├── SKILL.md             Zena persona + the full guided conversation
        ├── DISTRIBUTION.md      How to share/install: Claude Code, Cowork, other agents
        ├── scripts/competitor_scan.py  Skill entry (compute → author insights → --render)
        ├── scripts/core/        Vendored copy of the engine (via scripts/vendor.py)
        ├── references/onboarding.md
        ├── examples/            Sample combined report HTML
        └── tests/               test_competitor_scan.py + test_skill_md.py

scripts/
├── vendor.py                COPIES core/ engine into each skill's scripts/core/
├── capture_fixtures.py      Main fixture capture
└── probe_*.py               Edge-case + phase-B probes

tests/knowledge_base/        FOUNDATION REGRESSION (114 tests)
tests/test_zenabm_api.py     ZenABM API client tests
tests/test_zenabm_models.py  ZenABM model tests
tests/test_signals_zenabm.py Signal tests (ZenABM models)
tests/test_comparison.py     You-vs-them comparison tests
tests/test_report_html.py    HTML renderer tests

# Legacy (raw-LinkedIn; kept as CTO-brief reference - do not delete):
tests/test_core_client.py    Raw-LinkedIn client tests

ONBOARDING.md                START HERE if you're new - get up to speed fast
CLAUDE.md                    Directives for Claude Code sessions in this repo
HANDOVER.md                  Resume-later brief - read this to pick up work
.env.example                 Env template

# Paused / legacy sub-projects (not on the roadmap):
batch_lookup.py, db.py, ...  B2B outreach batch pipeline (paused; legacy client has known bugs)
app.py, src/agent/, ...      Streamlit chat agent (paused; see docs/TOOL_REFERENCE.md, USAGE_EXAMPLES.md)
```

---

## The `abm-competitor-intel` skill

An **agent-driven, conversational** skill. The user only chats; the agent runs the bundled Python behind the scenes.

**What it does:** the user pastes competitor LinkedIn URLs or names (keyword search kept as a discovery helper). Zena profiles each competitor's LinkedIn ad activity - share-of-voice, momentum, format mix - and produces a **you-vs-them** head-to-head comparison (activity/format/share-of-voice, scale vs. efficiency, and concrete recommended moves). Deliverable: one ZenABM-branded, self-contained, downloadable HTML report. Lean by default; expandable ABM detail inline.

**API:** runs entirely on the deployed **ZenABM API** (`https://app.zenabm.com/api/v1`) via one Bearer token. No direct LinkedIn calls; no MCP; no client-side caps (all limits and plan-gating are server-side; the skill degrades to a warm upsell on trial/expiry).

### 3-step onboarding

1. Sign up at https://app.zenabm.com/signup
2. Connect your LinkedIn ads account inside ZenABM and let it sync
3. Go to https://app.zenabm.com/api-keys - click **New Token** - **Generate** - **Copy**

Paste the token in chat. That is it.

### Install and use

The skill folder is self-contained - take just the `abm-competitor-intel` folder anywhere.

- **Claude Code:** drop the `abm-competitor-intel` folder into your project's `.claude/skills/` or into `~/.claude/skills/` (global). Or `git clone` this repo and run `claude` - it's auto-discovered. Then just say, e.g. "show me my competitors' LinkedIn ads."
- **Cowork / marketplace:** zip the `abm-competitor-intel` folder and upload it. The repo's `.claude/.claude-plugin/plugin.json` lets the whole repo install as a plugin too.
- **Org plugin monorepo:** the skill is destined for `ZENABM/linkedin-abm-skills` (contributed via PR + release zip). This workshop repo is where it is developed.

---

## Clone + verify on a fresh machine

```bash
git clone https://github.com/bilalahmad20/linkedin-ad-library-usecases.git
cd linkedin-ad-library-usecases
python3 -m venv .venv
source .venv/bin/activate
pip install requests pydantic python-dotenv pytest

# Confirm foundation + engine + skill are intact (offline, no token, no network):
python -m pytest tests/knowledge_base tests/test_zenabm_api.py tests/test_zenabm_models.py \
  tests/test_signals_zenabm.py tests/test_comparison.py tests/test_report_html.py \
  .claude/skills/abm-competitor-intel/tests -q
# expect: 385 passed
```

The full suite runs offline - no token, no network.

---

## Development workflow

- **Engine lives once in `core/`** and is copied into each skill by `scripts/vendor.py`. After changing any `core/` engine module, run `python3 scripts/vendor.py` so the skill's `scripts/core/` copy stays in sync, then run the tests.
- **Refresh fixtures** (rarely needed): `python3 scripts/capture_fixtures.py` with a valid token set as `ZENABM_TOKEN`.
- **Golden rule:** never report "not advertising" for an advertiser with no impression coverage - report "unknown". Enforced by `core/signals.py` and validated live.

---

## Foundation at a glance

| Metric | Value |
|---|---|
| Companies audited | 15 |
| Ads inspected | 1,563 |
| Distinct API call patterns probed | 48 |
| Fixture JSON files | 118 |
| Foundation regression tests | 114 (all green) |
| Full scoped suite | 385 (all green) |
| Real bugs found in legacy code | `countries` and `adType` params - both silently return 400 |

---

## License

See [`LICENSE`](LICENSE).
