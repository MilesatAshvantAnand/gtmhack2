# Design Spec — `abm-competitor-intel` (combined competitor skill)

> Written 2026-07-12. Evolves the existing `keyword-competitors` skill into one combined skill for the org repo **`ZENABM/linkedin-abm-skills`**.
> **Revised 2026-07-12** after the ZenABM API turned out to be deployed and to serve BOTH competitor and own data through one Bearer token — the architecture is now a single ZenABM API (no MCP, no LinkedIn token, no direct-LinkedIn calls).
> Builds on: `2026-07-06-zena-competitor-skills-design.md`, `2026-07-06-keyword-competitors-hardening-design.md`. Companion deliverable already shipped to the CTO: `docs/ad-library-api-for-zenabm-wrapper.md`. API reference: ZenABM API Postman docs (`documenter.getpostman.com/view/53042651/2sBY4LSNRP`).

---

## 1. Summary

Turn `keyword-competitors` into **`abm-competitor-intel`** — one skill that (1) profiles a set of competitors' LinkedIn advertising and (2) shows how the user's *own* advertising stacks up. Through-line: **know your competitors → see how you compare.** It matches the `linkedin-abm-skills` conventions (Zena persona, ZenABM branding, downloadable artifact) and is contributed via a fork-based PR + a maintainer-cut release zip.

**All data comes from one deployed API** — the **ZenABM API** (`https://app.zenabm.com/api/v1`, Bearer auth with a key from `app.zenabm.com/api-keys`). Competitor data via `/ad-library/*`; own data via `/linkedin-metrics`, `/creatives`, `/ad-spend`, etc. No MCP, no LinkedIn token, no direct-LinkedIn calls. All limits/plan-gating/token-revocation are enforced server-side, so the skill carries **no client-side caps** — it just calls the API and handles limit/expiry responses with a subtle upsell.

---

## 2. What changes vs. the current skill

| Aspect | Current `keyword-competitors` | New `abm-competitor-intel` |
|---|---|---|
| Name / command | `keyword-competitors` | **`abm-competitor-intel`** |
| Primary input | keyword | **competitor LinkedIn URLs**; keyword demoted to a flagged discovery helper |
| Output | competitor landscape | competitor landscape **+ you-vs-them comparison** |
| Data source | direct LinkedIn Ad Library + pasted token | **ZenABM API** (one Bearer token; competitor + own data) |
| Own data | none | ZenABM API own-data endpoints |
| Auth | pasted LinkedIn token, custom onboarding | **ZenABM API key** (`/api-keys`), org-standard Zena onboarding |
| Caps | client cumulative-cap ledger + `ZENA_DEV` | **none client-side** — server-enforced; subtle upsell on limit/expiry |
| Report | flat, over-detailed | **lean-by-default with expandable ABM detail** (progressive disclosure) |
| Delivery | claude.ai Artifact | **multi-platform**: Cowork `create_artifact`, Claude Code, claude.ai, file-fallback |
| Home | `linkedin-ad-library-usecases` | contributed to `ZENABM/linkedin-abm-skills` |

Development happens in **this repo** (`linkedin-ad-library-usecases`, where the engine + tests live): rename `.claude/skills/keyword-competitors/` → `.claude/skills/abm-competitor-intel/`, rework it, test; then copy the finished self-contained folder into a fork of `linkedin-abm-skills` for the PR (Phase C).

---

## 3. Product — the pipeline & flow

1. **Zena intro + pitch** (org persona, §5).
2. **Onboarding** — 3 steps, up front, each with an exact link (§5).
3. **Get input:** *"Who are your competitors? Paste their LinkedIn URLs."* (primary). Optional: *"Not sure who? Give me a topic and I'll find who's advertising on it — heads-up, that matching is approximate."* (keyword discovery, §9).
4. **Profile the competitors** (ZenABM `/ad-library/by-advertiser`): per competitor — activity level + share-of-voice, format mix, momentum, reach scale, targeting posture. → free competitor report.
5. **Compare to the user's own ads** (ZenABM own-data endpoints): the you-vs-them section — head-to-head (activity/format/SOV) **+** scale-vs-efficiency, woven.
6. **Deliver** one combined, ZenABM-branded, downloadable artifact (§6).

---

## 4. Data architecture — the ZenABM API (unified)

- **Base URL:** `https://app.zenabm.com/api/v1`. **Auth:** `Authorization: Bearer <api-key>` on every request (key from `app.zenabm.com/api-keys`). Deployed and live — build + test directly against it.
- **No MCP, no LinkedIn token, no direct LinkedIn, no forbidden-params guard, no client caps.**

### 4.1 Competitor data (public ad-library)
| Endpoint | Use |
|---|---|
| `GET /ad-library/by-advertiser?company=&companyId=&countries=&startDate=&endDate=&limit=` | Profile a named competitor. Accepts **`companyId`** (first-class) or `company` (name/slug); server does country/date filtering. |
| `GET /ad-library/by-keyword?keyword=&advertiser=&countries=&startDate=&endDate=&limit=` | Keyword discovery (flagged approximate, §9). |

**Normalized response** (`data`):
- `ads[]`: `adId`, `adUrl`, `isRestricted`, `type`, `advertiser{ name, url, companyId, payer }`, `statistics{ firstImpressionAt, latestImpressionAt, totalImpressions{from,to}, impressionsByCountry[{country, percentage}] }` **or `null`**, `targeting[{ facet, isIncluded, isExcluded, includedSegments, excludedSegments }]`.
- `advertisers[]`: rolled-up `{ name, url, companyId, adCount }` — gives per-advertiser ad counts directly (great for ranking + keyword discovery).
- `total`, `scanned`, `returned`, `truncated`.

Note the field renames vs. the raw LinkedIn shape: `statistics` (was `adStatistics`), `impressionsByCountry`/`percentage` (was `impressionsDistributionByCountry`/`impressionPercentage`), `country` is a plain ISO code (no `urn:li:country:` prefix), `facet` (was `facetName`), and `companyId` is now first-class. `statistics: null` = the EU-visibility gap (the golden rule still applies: null → unknown, never zero).

### 4.2 Own data (same token)
| Endpoint | Use |
|---|---|
| `GET /linkedin-metrics?startDate=&endDate=` | **Probe** (empty/error ⇒ not connected) + own aggregate: `costInUsd`, `impressions`, `clicks`, `engagements` → derive CTR/CPC/CPM. |
| `GET /creatives?cursor=&pageSize=&...` | Own ad catalog: `format`, `status`, `isServing`, campaign/ad-set linkage → own activity level + format mix. |
| `GET /ad-spend?startDate=&endDate=` | Own spend detail (summary + per-ad-set + monthly). |
| (available if needed) `/campaign-groups`, `/campaigns`, `/companies`, `/deals`, `/dashboard` | deeper own-side context. |

### 4.3 Engine changes
- **`core/client.py`** — rewrite to a ZenABM API client: Bearer auth, base URL, methods for the two `/ad-library/*` endpoints and the own-data endpoints; handle limit/plan/expiry error responses. Drop the LinkedIn-specific logic (forbidden params, 25-count pagination, direct base URL).
- **`core/schema.py`** — model the normalized ZenABM shapes (competitor `ads[]`/`advertisers[]`; own metrics/creatives/spend).
- **`core/signals.py`** — keep the signal logic (tier/golden-rule/momentum/reach/format/SOV) but point accessors at the new field names (`statistics`, `facet`, `companyId`, plain-ISO `country`). Update the 28 signal tests to the new shape. (Implementation choice for the plan: adapt-in-place vs. a thin wrapper→model adapter that preserves the existing tests.)
- **`core/report_html.py`** — reskin to org brand (logos), add Download-PDF button, progressive-disclosure sections (§6).
- **Retire:** `session_ledger.py` + `ZENA_DEV` + cap tests; the LinkedIn token / `LINKEDIN_ACCESS_TOKEN`; the forbidden-params guard.

---

## 5. Onboarding & persona (3 steps)

**Persona:** *Zena by ZenABM* — warm, concise, plain-English; **no emojis in chat**, hyphens not em-dashes; never name the model/Anthropic/Claude ("I'm Zena by ZenABM"); competitor data = *public advertising activity via ZenABM*, own data = *your own LinkedIn ads in ZenABM*. **Golden rule:** the user only chats; Zena does the technical work with short progress notes.

**Opening pitch (shape):** *"Hi, I'm Zena by ZenABM. I'll profile your competitors' LinkedIn ads — who they are, what they run, how loud they are — and show how your own advertising stacks up. You'll get a clean report you can download and share. It takes about two minutes to get set up — want me to walk you through it?"*

**Setup — conversational, one at a time, skip what's done, in this order:**
1. **ZenABM account** — *"Do you have a ZenABM account? If not, sign up free (no card) at `https://app.zenabm.com/signup`."* Wait for confirmation. (Required even for the free competitor report.)
2. **Connect LinkedIn in ZenABM** — connect the LinkedIn ads account and let it sync (powers the own-data comparison).
3. **Get the API token** — *"Go to `https://app.zenabm.com/api-keys`, click **New Token**, name it, click **Generate**, then **Copy** it and paste it here."* Zena stores it in the environment (`ZENABM_TOKEN`); the user never opens a terminal.

Then: ask for competitors/keywords → fetch → build. **Probe gate:** call `/linkedin-metrics` before promising own-data numbers; a tiny `/ad-library` call to confirm the token before promising competitor numbers. On a limit/expiry/plan error, deliver a warm, subtle upsell (trial ended / upgrade), never a hard cap message.

---

## 6. The report & delivery

**Presentation model: lean-by-default, with expandable ABM detail (progressive disclosure).** The default view is decision-first and skimmable; the depth an ABM/demand-gen analyst wants is one click away, not removed. Only true jargon is footnoted. (Directly fixes "too detailed and unusable" without dumbing it down.)

**Default (surfaced):**
- **3–5 plain-English takeaways** up top.
- **Per-competitor compact card:** advertising right now? · activity level (heavy/moderate/light) + **share-of-voice** · **format mix** · **momentum** (ramping / steady / cooling / dark).
- **The field at a glance:** loudest, who's ramping, who went dark (= opening), recurring rivals.
- **You vs them** (when own data present): keeping up on activity/consistency, **format gaps**, your **share-of-voice**, and **2–3 concrete moves**.

**Expandable "details" (kept, one click away — the ABM/demand-gen depth):** reach scale/ranges, geo/country split, **targeting posture** (broad vs. company/job-level = an ABM motion — high-value to this audience), ad **longevity / cadence** (always-on vs. bursty), per-ad breakdown, and your own efficiency metrics (CTR/CPC/CPM, spend).

**Footnote only:** EU-visibility / coverage-% / "tier" jargon → *"some advertisers show only limited public data."*

**Rendering:** keep the Python renderer, reskinned to org brand (`logo_white/dark.png`), light mode, self-contained inline CSS/JS, **inline SVG** charts, `✓/✗/—` not emoji, **Download-PDF button** (`window.print()`). Keep the two-step *compute → Zena authors insights → render*.

**Multi-platform delivery (required):** always write a self-contained **HTML file** (universal), then use the right mechanism per environment — **Cowork** `create_artifact` (+ WeasyPrint PDF), **Claude Code / claude.ai** Artifact where available, **Codex / others** file-only with the path. Detect + degrade gracefully.

---

## 7. Monetization

Free competitor report (token, requires ZenABM signup) is the hook; connecting LinkedIn + real own-data unlocks the you-vs-them comparison. **All metering is server-side** (rate, plan, token-revocation on trial end). The skill has **no client-side caps** and never says "you get N competitors" — it calls the API and, on a limit/plan/expiry response, delivers a **subtle** upsell. No cap ledger, no `ZENA_DEV`.

---

## 8. Competitor-by-URL mechanics

- **Input:** LinkedIn company-page URL (or name), several allowed. Parse the numeric ID from the URL when present → pass as **`companyId`**; else pass the slug/name as **`company`**. The API resolves + returns `advertisers[]` (name, companyId, adCount) so Zena can confirm the match. This is clean now — no local slug→ID heuristics needed. (Fuzzy-collision risk is the server's to handle; we confirm via the returned `advertisers[]`.)
- **Profile per competitor** via the existing signal set scoped to that advertiser: activity + SOV, format mix, momentum, reach scale, targeting posture, longevity.

---

## 9. Keyword discovery (secondary, flagged)

Keep keyword search as an optional *"find who's advertising on X"* step via `/ad-library/by-keyword`. Zena **flags it as approximate** (fuzzy full-text, no phrase matching — confirmed live) and steers toward naming real competitors. The `advertisers[]` rollup makes "who showed up + how many ads" easy; separate true category rivals from incidental mentions.

---

## 10. Repo integration (Phase C — after built & tested here)

1. **Fork** `ZENABM/linkedin-abm-skills` (contributor has read-only → fork-based PR).
2. **Add** `skills/abm-competitor-intel/`: `SKILL.md` (name=folder; trigger-rich `description` with "Use when… says things like… Do NOT use for…"; `compatibility` = the ZenABM API token, works in Cowork/Claude Code), `references/` (onboarding adapted from the sibling canonical file + API/signals refs), `assets/` (org logos + report template), optional `evals/`.
3. **Update "four → five" surfaces:** `README.md` (skills table, journey diagram, per-skill section, count wording, get-started) and `CLAUDE.md` (intro count, routing table, do-not-confuse bullets, layout tree); bump `version` in `.claude-plugin/plugin.json` + `marketplace.json`. `.mcp.json` unchanged (this skill doesn't use it; note that in the PR).
4. **Update the 1–2 sibling routing references** naming `keyword-competitors` (audit + report SKILLs) to `abm-competitor-intel` (routing string only, not behavior).
5. **Fork-based PR** to `main`.
6. **Release (maintainer-cut):** produce `abm-competitor-intel.zip` (single top-level skill dir, no repo-root files, no macOS cruft) + release-notes entry; a maintainer with write access attaches it to the GitHub Release and updates the body table. Contributor preps these; cannot cut the release.

---

## 11. Testing

- Keep the foundation/knowledge-base regression green. Rework the engine + skill tests for the ZenABM API shapes: a **fake ZenABM API client** (fixtures from the Postman example responses) drives offline tests of competitor profiling, keyword discovery, the comparison assembly (own-data fixtures), and multi-platform delivery selection. Remove retired ledger/`ZENA_DEV` tests.
- **Live smoke test (first implementation step):** with the user's real api-key, hit `/ad-library/by-advertiser`, `/ad-library/by-keyword`, and `/linkedin-metrics` to confirm the deployed shapes match the docs and to resolve the pagination/`limit`/`truncated` behavior empirically.

---

## 12. Out of scope (flagged)

- Competitor spend / CPC / CTR / ad copy (not public / not returned).
- Building or changing the ZenABM API (CTO owns it).
- Changing sibling skills' behavior (only their routing reference to this skill).
- Cutting the GitHub release / tag (needs maintainer write access).

---

## 13. Build order (phases)

- **Phase 0 — Live smoke test** of the ZenABM API with a real key (shapes + pagination).
- **Phase A — Competitor skill on the ZenABM API.** Rewrite the client to the API; rename to `abm-competitor-intel`; competitor-by-URL (companyId) + flagged keyword discovery; org Zena onboarding (3 steps) + brand assets + Download-PDF + multi-platform delivery + progressive-disclosure report; retire ledger/`ZENA_DEV`/LinkedIn-token. Ships the free competitor report.
- **Phase B — Own-data comparison.** Wire `/linkedin-metrics` + `/creatives` + `/ad-spend`; build the you-vs-them section (head-to-head + scale-vs-efficiency); probe-gate + subtle upsell on limit/expiry.
- **Phase C — Repo integration.** Fork, add the skill, update README/CLAUDE/manifests + sibling routing, PR; prep the release zip + notes for a maintainer.

---

## 14. Open items to verify (in the plan / smoke test)

1. Pagination/scan depth on `/ad-library/*` (`limit` / `scanned` / `truncated`) — how to get enough ads per competitor for reliable signals.
2. Exact own-data field shapes under real data (docs examples are representative; confirm live).
3. Environment detection for the artifact (Cowork `create_artifact` vs claude.ai Artifact vs file-only).
4. Whether `statistics: null` frequency under the wrapper matches the EU-visibility pattern (golden-rule handling).

---

## 15. Success criteria

1. Paste competitor LinkedIn URLs → a branded, downloadable, **lean** competitor report (free, works in Cowork + Claude Code).
2. Connecting real data adds a you-vs-them comparison (head-to-head + scale-vs-efficiency).
3. Keyword search works but is clearly flagged approximate/secondary.
4. Onboarding matches the org Zena convention: signup → connect LinkedIn → api-keys token; no MCP, no LinkedIn token.
5. Everything runs on the single ZenABM API Bearer token; no client-side caps; graceful subtle upsell on server limits.
6. The report is lean-by-default with expandable ABM detail — usable, not overwhelming, without losing what ABM/demand-gen buyers care about.
7. Clean self-contained skill folder drops into `linkedin-abm-skills`; installs via plugin (Claude Code) or release zip (Cowork).
