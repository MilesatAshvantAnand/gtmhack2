# PRD — LinkedIn Ad Library API Knowledge Base (Foundation)

**Author:** Claude (Opus 4.7) drafting for Bilal
**Date:** 2026-07-03
**Status:** Draft — awaiting approval

---

## 1. Problem

Every sub-project of this repo consumes the LinkedIn Ad Library API. Today the API's actual behavior lives in three fragile places: `src/services/linkedin_client.py` (code), `docs/LINKEDIN_API_OFFICIAL.md` (partial and outdated), and Bilal's head (institutional memory). Each new sub-project risks re-discovering the same limits, mis-typing a param, or building on an inference that was never validated.

We need one canonical, fixture-backed knowledge base that answers three questions definitively:
1. **What can the API do?** — every endpoint, every parameter, every accepted value, positive AND negative
2. **What does it return?** — every field, every type, every null case, with real examples
3. **What can we legitimately infer from what it returns?** — every derived signal + why the inference is safe (with the failure case that would invalidate it)

If we get this right once, all sub-projects consume from it and nothing needs re-audit unless LinkedIn ships an API change.

## 2. Users

- **Primary:** Future-Bilal building sub-project N — needs to answer "can I get X from this API?" in 60 seconds without reading source
- **Secondary:** Future-Claude implementing a sub-project — needs to know what's already validated so it doesn't waste context re-discovering
- **Tertiary:** Consumers of the shareable-skills sub-project — the skill's behavior is only as trustworthy as this knowledge base

## 3. Scope — in

- Exhaustive audit of the Ad Library endpoint (`GET /rest/adLibrary?q=criteria`)
- Every currently accepted param: `keyword`, `advertiser`, `countries`, `adType`, `start`, `count`
- Every rejected param confirmed via 400 response and archived: `advertiserUrn`, `dateRange.*`, `searchStartDate`, `searchEndDate`, `advertiserPageUrl`, `payer`
- Every response field on `AdsCreativeTransparencyEntity` and nested objects
- Every inferable signal currently computed in `batch_lookup.py` + a fresh review for new inferences we're missing
- Real fixtures from 5 companies chosen to span the diversity axes (EU-large-active, US-only-active, EU-small-active, dark-period, zero-ads/not-found)
- Auxiliary query shapes: keyword-only search, keyword+advertiser combined, country-filtered, `adType`-filtered
- Rate-limit + quota behavior + reset timing

## 4. Scope — out (non-goals)

- Ad detail scraping (`enrich_ads.py` scrapes the ad preview page — different API surface, out of scope for this doc)
- LinkedIn Marketing/Reporting API (a different product, only ever mentioned as "if you had ad manager access…")
- Any UI, dashboard, or workflow — this is a reference document
- Any code refactor — we can update `linkedin_client.py` to match the doc later
- Live monitoring or alerting on API changes (future concern)

## 5. Success criteria

The knowledge base is done when every one of these is true:

1. **Every response field** has an entry in `response-fields.md` with: type, null-case description, example value from a real fixture, and the sub-key path (e.g. `details.adStatistics.impressionsDistributionByCountry[].country`)
2. **Every claim** in the doc traces to a fixture file — no assertion without evidence
3. **Every currently-computed signal** in `batch_lookup.py` (all ~50) has an entry in `inferable-signals.md` with: derivation formula, prerequisite fields, validation rule that must be true for the inference to hold, and known false-positive case
4. **Every non-supported param** is listed in `constraints.md` with the exact 400 response captured as fixture
5. **The 5 test-company fixtures** collectively exercise: impression data full/partial/none, `is_currently_advertising` true/false, `is_dark_period` true/false, `is_ramping_up` true/false, `is_new_advertiser` true/false, `id_match` found/found_by_id/not_found
6. **Rate-limit behavior** documented: burst threshold, backoff we observed, 429 body shape, daily quota, reset time, per-token vs per-app limit
7. **A pytest suite** in `tests/knowledge_base/` loads each fixture and asserts every documented field is present (regression test — if LinkedIn changes their schema, this fails immediately)
8. **No PII** in fixtures — company-level only; no scraped contact data anywhere

## 6. Milestones — STATUS 2026-07-03

| # | Milestone | Cost | Output | Status |
|---|---|---|---|---|
| M0 | PRD approved + test companies chosen | ~0 API calls | This doc + `test-matrix.md` | ✅ Done |
| M1 | Capture fixtures for 15 companies + auxiliary + negative + call-pattern probes | ~165 API calls | 118 fixture JSON files | ✅ Done |
| M2 | Fill `endpoints.md` + `response-fields.md` + `call-patterns.md` from fixtures | 0 API calls | 3 docs, 675 lines | ✅ Done |
| M3 | Fill `inferable-signals.md` + 13 worked example derivations | 0 API calls | 881-line doc | ✅ Done |
| M4 | Fill `constraints.md` (14 sections, every constraint fixture-backed) | 0 API calls | 194-line doc | ✅ Done |
| M5 | Pydantic models + JSON schema + pytest regression suite | 0 API calls | `core/schema.py` + 5 JSON schemas + `tests/knowledge_base/` (114 tests, all green) | ✅ Done |
| M6 | Bilal review + merge | 0 API calls | Merged commit on main | ⏳ Pending |

**Total API budget spent:** ~165 calls across 3 rounds (well within one day's 1,000-call quota). Fixtures captured once and versioned. Regression suite catches drift the moment LinkedIn changes the schema.

## 7. Risks

| Risk | Mitigation |
|---|---|
| LinkedIn changes API mid-audit | Pytest regression suite catches it on next fixture refresh; version fixtures with capture date |
| Test companies don't exercise a rare code path (e.g. `SPONSORED_INMAILS`) | After initial audit, cross-reference `batch_lookup.py` `AD_TYPE_MAP` — any type not seen in fixtures gets its own targeted capture |
| Inferences we currently make in `batch_lookup.py` are wrong | The audit MUST re-derive each one from first principles and flag those that don't hold |
| Fixture staleness | Add a `captured_at` field to each fixture; regenerate quarterly or on suspected API change |
| Scope creep — knowledge base becomes a full refactor | Non-goal: no code changes in this phase. Findings that require code changes get filed as sub-project tickets. |

## 8. New inferences to consider (audit output — TBD)

Placeholder for signals we currently DON'T compute but might be able to. The audit fills this. Seeds from external research so far:

- **Audience overlap indicator** — if two companies target identical `adTargeting` slices, competitive proximity signal
- **Payer-vs-advertiser mismatch** — `adPayer != advertiserName` may indicate agency-run campaigns (already partially captured as `ad_payer_differs`)
- **Country expansion pattern** — new `impressionsDistributionByCountry` entries over time = geographic expansion
- **Cadence anomaly** — gap between `firstImpressionAt` and `latestImpressionAt` vs number of ads = burst vs always-on strategy

These are hypotheses only — validated during M3.

## 9. Open questions for Bilal — RESOLVED

- [x] API budget: expanded to ~165 calls after two rounds of gap-filling; still <17% of one day's quota. Approved by user 2026-07-03.
- [x] Test companies: 5 diversity picks + user's 2 (Userpilot, ZenABM) → 7 initial. Expanded to 15 in round 2 for gap coverage. Plus ad-hoc Phase B probes for SPOTLIGHT_V2 hunt, restricted-ads hunt, Skill 1 keyword competitors.
- [x] Regression suite: fixtures-only (approved). Live-drift check is a manual on-demand step.
- [x] First sub-project: **shareable skills** (user's priority). Two initial skills defined 2026-07-03 — see `docs/architecture.md`. B2B outreach paused.

## 10. Definition of done

Merged to `main` with:
- All 7 files in `docs/api-knowledge-base/` populated (README already done)
- `tests/knowledge_base/` passing green against saved fixtures
- `CLAUDE.md` in repo root updated with a pointer: "For API behavior, see `docs/api-knowledge-base/`"
- One "definition of every field" cheatsheet (auto-generated from response-fields.md would be a stretch goal)
