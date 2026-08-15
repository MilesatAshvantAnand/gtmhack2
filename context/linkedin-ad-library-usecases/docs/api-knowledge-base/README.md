# LinkedIn Ad Library API — Knowledge Base

**Status:** Foundation phase — **audit complete (2026-07-03)**, awaiting review + pytest regression suite.
**Purpose:** The single source of truth for what the LinkedIn Ad Library API returns, what we can infer from it, and what its limits are. Every sub-project (B2B outreach, shareable skills, and anything future) consumes from these files instead of re-deriving.

**Corpus:** 1,075 ads across 15 companies + 5 auxiliary queries + 6 negative-test fixtures. All captured 2026-07-03. Every claim in these docs traces to a fixture path.

## Index

| File | Purpose | Status |
|---|---|---|
| [`PRD.md`](./PRD.md) | Product requirements for the foundation phase | ✅ |
| [`external-references.md`](./external-references.md) | Research summary: reusable repos, official docs, comparable products | ✅ |
| [`test-matrix.md`](./test-matrix.md) | 5 initial companies + query shapes; round-2 added 10 more | ✅ (round 1) — round-2 companies documented inline in other files |
| [`endpoints.md`](./endpoints.md) | Endpoint spec + accepted params + response envelope + error shapes | ✅ |
| [`call-patterns.md`](./call-patterns.md) | **Case-based: for every way to call the API, what response you get and why.** Start here. | ✅ |
| [`response-fields.md`](./response-fields.md) | Every field returned, types, coverage %, examples, null cases | ✅ |
| [`inferable-signals.md`](./inferable-signals.md) | Every derived signal with formula, prerequisites, corpus validation, failure cases | ✅ |
| [`constraints.md`](./constraints.md) | Rate limits, DSA rules, rejected params, ordering, quota, restricted-ad gap | ✅ |
| [`fixtures/`](./fixtures/) | 66 raw JSON response files, versioned truth | ✅ |

## Reading order for a new consumer

## Reading order for a new consumer

1. `PRD.md` — why this exists
2. `constraints.md` — what the API cannot do (avoid dead ends)
3. `endpoints.md` + `response-fields.md` — what it can do
4. `inferable-signals.md` — derived intelligence layer
5. `fixtures/` — dig in when you need a concrete example
