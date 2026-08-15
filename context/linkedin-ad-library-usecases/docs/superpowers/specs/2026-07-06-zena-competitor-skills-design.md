# Design Spec — Zena competitor-intelligence skills

**Date:** 2026-07-06
**Status:** Approved design → ready for implementation planning
**Scope of this spec:** the shared platform + **Skill 1 (keyword competitors)** in full detail. Skill 2 (5-competitor comparison) is sketched at the end; it gets its own plan and reuses this foundation.

---

## 1. Summary

Two shareable **Claude Skills**, branded as **Zena** (ZenABM's agent), that let a marketer understand competitors' LinkedIn advertising and see how they stack up — then earn the ZenABM upgrade. Each skill is **self-contained** (a folder with `SKILL.md` + a bundled, dependency-free engine) and independently installable on Claude Code / Cowork / claude.ai.

- **Keyword skill (built first):** user gives up to 5 keywords/themes → the skill finds who's advertising on each in the LinkedIn Ad Library, ranks the field by share-of-voice, flags momentum (new/ramping/steady/cooling/dark) and format mix, and outputs a **self-contained, ZenABM-branded HTML report**.
- **Comparison skill (built second):** user gives up to 5 competitors → profile each from the Ad Library and set them against the user's **own** performance pulled from the **ZenABM MCP**.

Everything is grounded in the fixture-backed API audit in `docs/api-knowledge-base/` — we never re-derive API behavior.

## 2. Users & value

**Users:** demand-gen, ABM, and performance marketers running LinkedIn ads. Non-technical; they want answers, not analysis homework.

**Value:** in minutes, honest competitive intelligence they can share with their team — "who owns this theme, who's moving, where the whitespace is" — with a clear, non-pushy path to ZenABM for the deeper/automated version.

## 3. Distribution & packaging

**Format:** standalone, self-contained skills using the `.claude/skills/<name>/` layout (mirrors `emikor/ads-skills`), **plus** a `.claude/.claude-plugin/plugin.json` (mirrors `emikor/gtm-strategist-skills`) so the same repo also installs via Cowork/marketplace. Not a monolithic plugin — each skill folder stands alone.

**Repo layout:**
```
core/                         pydantic API models + KB regression suite (existing, fixture-tested) — the reference
engine/                       stdlib-only SHIPPING engine (client.py, signals.py, report_html.py) — single source of truth
  tests/                      fixture-driven tests for the stdlib engine (behaviour checked against core/'s corpus)
scripts/vendor.py             COPIES engine/*.py into each skill's scripts/ (a copy step, not a transform)
.claude/
  .claude-plugin/plugin.json  enables Cowork / marketplace install
  skills/
    keyword-competitors/      self-contained; independently uploadable
      SKILL.md                name + MANDATORY TRIGGERS description + routing
      scripts/                vendored engine copy + keyword_scan.py (skill-specific entry)
      references/             onboarding.md (Zena persona + setup), brand/report notes
      examples/               sample-report.html (offline, from a fixture)
    competitor-comparison/    built second, same pattern (+ MCP-orchestrated own-data)
CLAUDE.md                     shared Zena identity/behaviour (git-clone path)
README.md  INSTALLATION.md  .env.example
```

**Self-containment:** each skill bundles its own copy of the engine, so a marketer can take *one* skill and upload it to claude.ai or drop it into Claude Code. Reuse happens at **development** time: the stdlib engine is maintained once in `engine/` (the shipping source of truth) and **copied verbatim** into each skill's `scripts/` by `scripts/vendor.py`. `core/` (pydantic) is a separate, fixture-validated reference/regression layer — not shipped — that the stdlib engine's behaviour is checked against. (The plan decides whether `core/signals`/`core/client` from Phase 2 are kept as reference or retired in favour of `engine/`.)

**Distribution paths (document all three, per gtm-strategist):**
- Claude Code: `git clone` → `cd` → `claude` (skills auto-discovered); or drop a skill folder into `~/.claude/skills/`.
- Cowork: select the folder; `plugin.json` is picked up.
- claude.ai: upload the self-contained skill folder into a Project.

**Runtime constraints (honest):**
- **Claude Code / Cowork = guaranteed runtime** — bundled scripts run with full network + code execution. This is the primary target.
- **claude.ai = best-effort** — code execution is sandboxed (90s cap, no `pip install`, network access is workspace-dependent). Mitigation: the engine is **stdlib-only** (`urllib`+`json`, no `requests`/`pydantic`) so it needs no install; document that live fetching requires a network-enabled workspace.
- **Future cross-surface fix (noted, not built):** when ZenABM's MCP exposes an Ad-Library tool, the skill can fetch competitor data server-side with zero client network — works everywhere. Out of scope now.

## 4. Onboarding & Zena persona

**Zena persona (in `CLAUDE.md` + bundled per skill):** professional, concise, plain-English, no emojis, industry-aware. Identity guardrail: always "Zena by ZenABM"; never names the underlying model or discusses internals. Style: hyphens, not em/en dashes (ecosystem convention).

**Keyword skill onboarding = Ad-Library token only.** Conversational `/onboarding`-style flow that stops at the first step already done:
1. **Sign up** at `https://app.zenabm.com/signup` (skip if they have an account).
2. **Connect LinkedIn** inside ZenABM (required before a token exists); let it sync.
3. **Get the Ad Library token** → `[[TOKEN_URL_PLACEHOLDER]]` (`https://app.zenabm.com/bilal` looks user-specific; confirm the generic path). Paste it → written to a local `.env` as `LINKEDIN_ACCESS_TOKEN` (gitignored).
4. Note: tokens expire (~26 days; 401 / `serviceErrorCode 65602`) → regenerate and re-paste.

No MCP and no ZenABM API key for the keyword skill.

**Comparison skill onboarding (later)** adds: install the **ZenABM MCP** custom connector (`https://app.zenabm.com/api/mcp`, OAuth sign-in — no key to paste) so Zena can read the user's own data.

## 5. Architecture — the engine

The shippable engine lives once in `engine/` as **stdlib-only** modules (ported from the logic proven in `core/`), and `scripts/vendor.py` copies it into each skill's `scripts/`:

- `client.py` — LinkedIn Ad Library client over `urllib` (no `requests`). Sends only valid params (`q=criteria`, `advertiser`/`keyword`, `start`, `count≤25`); never the rejected `countries`/`adType`/etc.; 429 backoff; pagination.
- `signals.py` — pure, tier-aware signal functions on plain dicts (ported from `core/signals`): dedupe by canonical company id, `impression_data_coverage`, coverage-gated Tier S/T signals (the golden rule: unknown → omit/None, never "no"), share-of-voice, momentum status, format/funnel mix, EU-visible reach ranges, `advertiser_type` (company vs individual), "ad-duration = performance proxy."
- `report_html.py` — self-contained ZenABM-branded HTML renderer (see §6).
- `keyword_scan.py` — the skill's CLI entry: token + keywords in → fetch → analyze → write HTML.

`core/` (pydantic) stays as the fixture-validated reference + regression suite; the bundled stdlib engine gets its own fixture-driven tests mirroring that coverage.

## 6. The report (self-contained HTML, "Type A")

**One `.html` file, everything inlined**, no external requests (Artifact-CSP-safe): inline `<style>`, inline data, **charts as pure-CSS bars + hand-drawn inline SVG** (no chart libraries), responsive, print-to-PDF friendly, ≤16 MiB.

**Sections (exec-summary-first):**
1. Scope bar — keywords, geographies, # advertisers found, "last refreshed" date.
2. **Executive summary** — the 5 things that matter (signal → implication, plain English).
3. **Share-of-voice leaderboard** — horizontal CSS bars; basis stated (ad volume + EU-visible reach, *not* spend); the user highlighted if known.
4. **Momentum board** — new / ramping / steady / cooling / dark, with dates + direction.
5. **Format & funnel mix** — how the field plays the theme; empty lanes = whitespace.
6. **Reach (EU-visible)** — ranges with a confidence tag; never point numbers.
7. **Whitespace & threats** — opinion-labeled ("Our read:").
8. **Method & coverage note** — the 2-3 honest caveats, consolidated.
9. **Upgrade teaser** — footer callout.

**Branding (verbatim from ZenABM production CSS):** primary `#004737`, accent `#0f8a5f`, mint `#87ffc0`, cream surfaces `#f4f1e8`/`#f7f6f1`; status green `#00bb7f` / amber `#f99c00` / red `#ff6568`; borders `#e5e5e5`, zebra `#f5f5f5`, secondary text `#737373`; 10px base radius; subtle green→mint / cream gradients; Poppins/Montserrat with system fallbacks (real fonts embeddable later); inline green wordmark SVG. Full token set in the renderer.

**Delivery & sharing:** always write the `.html` file; on claude.ai also publish as a shareable Artifact; tell the user the share options (Artifact link / email the file / Netlify Drop / print-to-PDF).

## 7. Keyword skill — flow

1. Invoke → Zena welcome (in character).
2. Onboarding (§4) — detect setup; get the token if needed.
3. Ask input: up to **5 keywords/themes**.
4. Run `keyword_scan.py`: for each keyword, page the Ad Library, dedupe advertisers by company id, split companies vs individuals (individuals counted, hidden by default), compute signals + SOV + momentum.
5. Build the HTML report (§6).
6. Deliver: write file → (claude.ai) publish Artifact → present share options.
7. Zena gives the "5 things that matter" in chat + the report link, then the upgrade teaser.

## 8. Trust framing & actionability boundary

- **Coverage-first, ranges not points.** State the one honesty rule once up front ("US-only advertisers aren't in LinkedIn's EU transparency data — they may be more active than shown"), then show ranges confidently. Cap caveats at 2-3; consolidate the rest into the method note.
- **Each insight pairs with a one-line "what we can't see"** — factual, not apologetic.
- **"US-only = not visible," never "not advertising."** Only an explicit `no`/`False` with coverage present means it genuinely isn't happening.
- **Opinions are labeled** and carry, when it's a real recommendation, "act at your own risk; ZenABM's consulting package can walk you through it." No decision-load dumped on the user.
- **Plain English** throughout — translate every bit of jargon.

## 9. Freemium teaser & limits

- Hard cap: **5 keywords** (comparison skill: 5 competitors). Deliver full value within the cap; the cap itself is the pitch.
- Named upgrade unlocks (named, not built): competitor **creative/messaging** (hooks/offers/CTAs/landing pages — a later scraping skill), the **full field beyond 5**, **always-on tracking + weekly email/alerts/webhooks**, and the **consulting package** (`https://zenabm.com/book-a-demo`).
- Teasers placed where the reader just felt the limit (after SOV/format; on the "field of N"; on the momentum snapshot). One line each; never blocks delivered value.

## 10. Testing plan

- **Fixture-driven unit tests** for the bundled engine (dedupe, coverage gating/golden rule, SOV, momentum, advertiser_type, HTML renders) — no network/token, run in `.venv`.
- **Offline example**: `examples/sample-report.html` generated from `fixtures/phase-b/skill1_kw__product_analytics.json`.
- **Live smoke test** (secure): user puts the token in a local `.env`, runs a one-line command; it prints coverage %, counts, a sample advertiser (no secret in transcript). Confirms Ad-Library scope + real data.
- **First live report**: once the engine is wired, generate the first ZenABM-branded report from real data as the "see it early" checkpoint.
- The existing 187-test suite stays green.

## 11. Open placeholders (non-blocking)

- `[[TOKEN_URL_PLACEHOLDER]]` — the generic Ad-Library token page inside ZenABM (the `/bilal` URL looks personal). User will supply.
- Real-font embedding (Poppins/Montserrat WOFF2) — optional later polish; system fallbacks for now.

## 12. Build order (milestones)

1. **M1 — Scaffold & vendor tooling:** function-named skill folders, `scripts/vendor.py`, `plugin.json`, `CLAUDE.md`, `.env.example`.
2. **M2 — Bundled stdlib engine:** `client.py` (urllib) + `signals.py` (dict-based, tier-aware) + tests vs fixtures.
3. **M3 — HTML report renderer:** `report_html.py` (ZenABM branded, Type A) + tests + offline `sample-report.html`. **Checkpoint: user reviews the sample report.**
4. **M4 — Keyword skill wiring:** `keyword_scan.py` + `SKILL.md` (Zena persona, onboarding, triggers, teaser) + `references/onboarding.md`. **Checkpoint: live smoke test with real token.**
5. **M5 — Review & docs:** code-review pass; `README.md` + `INSTALLATION.md` (three surfaces); verify suite green.
6. **M6 — Comparison skill:** own spec + plan; reuses the foundation, adds MCP-orchestrated own-data + "Type B" report.

## 13. What the comparison skill reuses (M6 preview)

Same onboarding, engine, HTML renderer, persona, trust framing, teaser. Adds a per-competitor profile + side-by-side matrix and the un-copyable **you-vs-field** panel (their visible activity vs your real spend/CTR/pipeline). Own-data source: see the addendum (REST, not MCP).

---

## 14. Addendum — final built state (2026-07-06, live-validated)

Supersedes earlier detail where they differ:

- **Distribution:** built as a self-contained skill at `.claude/skills/keyword-competitors/` (SKILL.md + bundled `scripts/core/` engine + `references/` + `tests/`), plus `.claude/.claude-plugin/plugin.json`. `scripts/vendor.py` copies `core/` into the skill; confirmed it runs standalone from its own bundled engine. (Supersedes the `projects/*` layout.)
- **Engine:** reuse `core/` directly (pydantic) + `pip install requests pydantic python-dotenv` at setup — NOT a stdlib rewrite (supersedes §3/§5 "stdlib engine"). Only `core/report_html.py` is stdlib-only.
- **Report:** ONE combined multi-keyword report (cross-keyword summary → per-keyword sections → cross-theme rivals roll-up), ZenABM-branded, self-contained HTML, global links (no geo filter), plain 5th-grade headings.
- **Insights (two-step):** `keyword_scan.py` computes signals + writes `report_data.json` + a digest; **Zena authors** deep, plain-English, signal-linked insights into the JSON; `--render` bakes them into the final report. Exec summary = pure insight; ZenABM subtle in the body; strong CTA at the end.
- **Free-tier caps:** 3 keywords / top 5 competitors / **200** ads per keyword (was 500). Enforcement model in `docs/free-tier-enforcement.md` (client-side caps + a ZenABM server-side gate; pending CTO).
- **Comparison skill (skill-02):** own-data via ZenABM **REST API** (`sk_live_` key), optional MCP fallback (decision in §8 / free-tier-enforcement.md). Pending user go-ahead after they test skill-01 end-to-end.
- **Status:** keyword skill built, self-contained, hardened, **197 tests green** (merged to `main` via PR #2), and **live-validated end-to-end** against a real token — golden rule, agency/payer attribution, thought-leader "promoted by", and geo splits all confirmed on real data.
- **Hardening (2026-07-06, PR #2):** free-tier cap is now 3 keywords cumulative & per-token lifetime (token-keyed `.claude/skills/keyword-competitors/scripts/session_ledger.py`; NOT per-run, NOT a 24h window); share-of-voice ranking fix; cap-size/bypass flags gated behind `ZENA_DEV=1`; keyword param confirmed to support no precision operators (`docs/api-knowledge-base/call-patterns.md` §4g). See `docs/superpowers/{specs,plans}/2026-07-06-keyword-competitors-hardening*`.
