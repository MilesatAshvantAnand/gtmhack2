# Design Spec — Hardening the `keyword-competitors` skill

> Written 2026-07-06. Builds on `2026-07-06-zena-competitor-skills-design.md` (read its §14 addendum first).
> Scope: close free-tier loopholes, fix a ranking bug, improve keyword-match honesty, and strengthen the pull to ZenABM — driven by gaps found in a real end-to-end test session.

---

## 1. Summary

The `keyword-competitors` skill works, but a live test exposed that it is **not strict** and **does not reliably pull the user back to ZenABM**. This spec hardens four areas and adds a deep adversarial loophole pass:

1. **Free-tier enforcement** — turn the "3 keywords" limit into a **cumulative hard cap per conversation** (behavioral rules + a technical backstop), and treat combined/cross-theme multi-run analysis as paid.
2. **Ranking fix** — stop the ranker from burying high-volume, limited-visibility advertisers (the bug that forced a mid-conversation self-contradiction).
3. **Keyword-match honesty** — confirm empirically that precision cannot be improved server-side, then formalize agent-layer relevance triage (never dropping data).
4. **CTA overhaul** — one strong, specific pull to ZenABM per delivery; remove all self-undercutting language.
5. **Deep loophole-hardening pass** — adversarially probe SKILL.md + code for other bypasses and fold findings into rules and tests.

Non-negotiable: the full suite stays green (177 today) and grows.

---

## 2. Motivation — what the test session showed

From the pasted transcript:

- **Sequential-run keyword bypass.** After a 3-keyword report, the user said "run the analysis on the other 2 keywords." Zena replied *"a free run covers up to 3 keywords, so these two fit comfortably in a fresh run. No upsell needed for this one"* — delivering 5 keywords for free. `keyword_scan.py:run()` enforces the cap **per invocation** (`keyword_scan.py:1058`) with **no cross-run state**, so this is an architectural hole, not just a wording slip.
- **Free paid features.** Zena then produced a **combined 5-theme cross-competitor analysis** and offered to **render a persistent combined report** — both described by the skill's own copy as paid.
- **Ranking self-contradiction.** Zena first called ABM "a one-horse race (UserGems)", then had to correct itself: *"Multiply is running 45 ABM ads (~25% share)… but it ranked low because limited visibility."* Root cause: `_rank_key` (`keyword_scan.py:500`) sorts by `is_currently_advertising` **first**, and that signal is `None` (unknown) for limited-visibility advertisers — so a confirmed-active advertiser with 1 ad outranks a limited-visibility one with 45. The golden rule ("limited visibility ≠ small/inactive") is honored in the *signals* but violated in the *ranking*.
- **Bad keyword matches.** "Wood Mackenzie" (energy research) and "Aon" (reinsurance) ranked on "product analytics." The API `keyword` param is a fuzzy full-text match against ad **body copy**, which the API **does not return** (`response-fields.md:13` — the creative lives behind `adUrl` and must be scraped). Quotes are **not** honored as phrase markers (`call-patterns.md §4c`). So exact matching is impossible server-side, and client-side text filtering is impossible (no text to filter).
- **Weak, undercut CTA.** The chat CTA was soft and, in one place, explicitly cancelled ("No upsell needed for this one").

---

## 3. Free-tier enforcement (the core change)

### 3.1 Policy

- **3 distinct keywords TOTAL per conversation.** Not per run.
- **Top 5 competitors / 200 ads per keyword** unchanged.
- **Paid, and refused warmly:** any keyword beyond the 3rd; "run the other ones"/fresh runs to add keywords; any **combined or cross-theme analysis across runs**; a persistent/always-on combined report; more than top-5 competitors; the own-data (ZenABM) comparison.

### 3.2 Layer A — behavioral (primary fix, in `SKILL.md`)

Behavior-only enforcement is exactly what failed, so the rules must be rewritten to be **rationalization-proof**, naming the specific loopholes:

- The cap is **cumulative for the whole conversation**. Count distinct keywords already scanned in this conversation; once 3 are used, **do not scan more under any framing** — not "a fresh run," not "these fit in the free tier," not "no upsell needed."
- **Never** produce a combined/cross-theme view spanning more than one run, or offer to. That is a paid, always-on ZenABM feature.
- When the user asks for more, **refuse warmly and make the refusal the upsell** (see §6): name what they'd get in ZenABM, tie it to a gap already found, give the link.
- Remove every self-undercutting phrase. There is always an upsell at the boundary.
- Mandate a **single stable working directory** for the whole conversation (do not switch out-dirs between runs).

### 3.3 Layer B — technical backstop (defense-in-depth, in `keyword_scan.py`)

A **session ledger** the script maintains so accidental/rationalized bypass is blocked even if the agent forgets:

- **Location:** `~/.zena/ledger.json` (create dir if missing). Fallback to `$TMPDIR/zena-ledger.json` if home is not writable. Overridable via `--session-file PATH`.
- **Key:** `sha256(token)[:16]` — **never store the raw token.** Token is read from the same env resolution the client uses (`ZENABM_TOKEN` → `LINKEDIN_ACCESS_TOKEN`).
- **Record per key:** `{ "keywords": [<normalized distinct keywords>], "first_seen_ms": int, "last_seen_ms": int }`.
- **Normalization:** reuse `_parse_keywords` normalization (strip, casefold, collapse internal whitespace) for dedup so "Product Analytics" == "product analytics".
- **Per-token lifetime cap (updated 2026-07-06 per user decision):** the 3-keyword cap accumulates for the life of the token with **no time-based reset** (`session_window_ms=None`). Token rotation (~26 days) is the natural reset; an optional `session_window_ms` can restore a windowed reset if ever wanted. (The earlier 24h "per conversation" window was dropped in favor of the stricter lifetime cap.)
- **Enforcement on a run:** re-scanning a keyword already in the ledger is free (same keyword, not new). For genuinely new keywords, admit only up to `MAX_KEYWORDS − len(already_used_distinct)`; scan those, refuse the overflow with an upsell line, and if **zero** fit, refuse the whole run with the upsell. Persist the union (capped) back to the ledger.
- **Token-keyed + stable path** means the run-2 trick (new out-dir) does **not** reset the count.
- **Testability:** `now_ms` is already injected; add injectable `session_file` path and a `--no-ledger` flag (used by existing offline tests to stay deterministic). A `--reset-session` flag clears the current token's entry (dev/testing).

### 3.4 Honesty about the boundary

Per `docs/free-tier-enforcement.md`, this is **best-effort UX, not a security boundary** — a determined user on their own machine can bypass it. The durable gate is the ZenABM server-side proxy (pending CTO, out of scope here). The backstop exists to stop the *accidental and rationalized* bypass the transcript showed.

---

## 4. Ranking fix

Replace `_rank_key` so **share of voice (ad volume) is primary**, visibility can never bury volume:

```
new key (all descending):
  1. n_ads_on_keyword         # share of voice — robust across visibility tiers
  2. linkedin_maturity_score  # format sophistication
  3. active_tiebreak          # {True: 2, None: 1, False: 0} — low-weight tiebreaker only
```

- A 45-ad limited-visibility advertiser now ranks near the top regardless of missing reach data.
- The digest and report must **surface each shown competitor's visibility/coverage** so Zena narrates it honestly on first mention — no more contradictions.
- Update `tests/test_keyword_scan.py` expectations; add a regression test asserting a high-volume `coverage="none"` advertiser ranks above a low-volume confirmed-active one.

---

## 5. Keyword-match honesty

### 5.1 Confirm the limit empirically (live, needs a token)

Add `scripts/probe_keyword_precision.py` that probes query forms and records `paging.total` for each, to state definitively that precision cannot be improved server-side:

- baseline single/multi-word; quoted phrase (re-confirm §4c); punctuation/boolean-ish forms (`+`, `AND`, `,`); casing; leading/trailing space.
- Save responses as fixtures under `docs/api-knowledge-base/fixtures/keyword-precision/`; append the conclusion to `call-patterns.md §4` and, if it hardens a rule, `constraints.md`.
- **Gating:** this is the only token-dependent step. Everything else lands offline. The agent will request a current token when running it (tokens expire ~26 days).

### 5.2 Agent-layer relevance triage (in `SKILL.md`)

We cannot filter matches (no ad text), so precision is an **interpretation** concern, done honestly:

- Surface **all** matched advertisers in the digest — nothing dropped (golden rule).
- Add an explicit SKILL.md step: after reading the digest, Zena classifies each shown advertiser as **category rival** vs **incidental mention** (ad merely contains the words), using its own knowledge, and **labels it in the report `read` and takeaways** ("not an analytics tool — its ad just mentions the phrase").
- When a theme is **noisy** (high total, low top-share, several off-category names), Zena proactively offers a **tighter keyword** and explains multi-word narrows the field (`§4b`: "product management crm" → 4.8k vs 410k).
- No change to `scan_keyword_ads` counting — counts and share-of-voice stay honest.

---

## 6. CTA / pull-to-ZenABM overhaul (in `SKILL.md`)

- **One strong CTA per delivery**, specific and tied to a gap just found (e.g. "you found two heavy ABM advertisers you can't fully see — that's exactly what ZenABM tracks weekly; here's the demo link"). Not generic, not repeated nagging.
- Rewrite "Delivering" and "Free-tier limits and upgrade" sections; delete all undercutting language.
- **At the cap, the refusal is the upsell** — name the paid capability, tie to the finding, give `https://zenabm.com/book-a-demo` / signup.
- Keep the report's end CTA and the chat CTA consistent (same offer, same link).
- Persona rules unchanged (no emojis, hyphens not em-dashes, never reveal source/model).

---

## 7. Deep loophole-hardening pass

Beyond the four fixes, adversarially find other bypasses (the user asked for "deep tests"):

- **Parallel agents:** (a) red-team — simulate a user trying to extract more than the free tier (e.g. "just the names," "re-run with a synonym," "combine what you already have," "one more as a favor," multi-turn erosion); (b) auditor — read SKILL.md + `keyword_scan.py` for gaps (state that resets, framings that dodge the cap, places the CTA can be skipped).
- Consolidate confirmed findings → each gets a SKILL.md rule and, where mechanizable, a test.
- Report residual best-effort gaps that only a server-side gate can close.

---

## 8. Testing

- Keep the current suite green (177) and add:
  - **Ledger/cap unit tests** — cumulative count across runs, session-window reset, token-keying, re-scan-is-free, overflow refusal, `--no-ledger`/`--reset-session`. Use injected `now_ms` + temp `session_file`; no network.
  - **Ranking test** — high-volume `coverage="none"` ranks above low-volume active.
  - **Precision fixtures** — from §5.1 (added to the KB regression if they encode a rule).
  - **Behavioral eval (best-effort)** — extend `.claude/skills/keyword-competitors/evals/` with cap-refusal scenarios if practical.
- **Vendoring:** ledger + ranking live in `keyword_scan.py` (skill-specific, not vendored `core/`), so no re-vendor is needed for them. If any `core/` engine module changes, run `python3 scripts/vendor.py` and re-run the suite.

---

## 9. Out of scope (flagged, not done)

- Filling the placeholder token URL (HANDOVER #1).
- Skill-02 (competitor comparison).
- The ZenABM server-side enforcement proxy (`docs/free-tier-enforcement.md`, pending CTO) — the only thing that makes the cap a true security boundary.
- Scraping `adUrl` preview pages for creative text.

---

## 10. Success criteria

1. Asking for keywords 4-5 in any framing is **refused** with a specific ZenABM upsell, in both SKILL.md rules and the `keyword_scan.py` backstop (verified by tests).
2. No combined/cross-theme multi-run analysis is produced or offered for free.
3. A high-volume limited-visibility advertiser ranks in the top 5 (no more self-contradiction), verified by a test.
4. The keyword-precision limit is empirically confirmed and documented; the skill labels incidental matches instead of presenting them as rivals.
5. Every delivery ends with one specific, non-undercut ZenABM CTA.
6. Full suite green; new tests cover the cap, the session window, and the ranking fix.
