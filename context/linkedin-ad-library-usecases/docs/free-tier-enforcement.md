# Free-tier enforcement & anti-abuse — for review (CTO)

**Status:** open decision. The skill will enforce what it can on the client; the hard gate must live in ZenABM's backend. This doc is the shareable summary.

## The free-tier limits (what a non-paying user gets)

| Limit | Value | Why |
|---|---|---|
| Keywords (cumulative, per-token lifetime) | **3** | Enough to be useful; a clear reason to upgrade |
| Competitors shown per keyword | **top 5** | Real value; the rest are teased ("N more — upgrade") |
| Ads scanned per keyword | **200** | ~8 API pages; reliably ranks the field without blowing the daily token quota; framed honestly ("top 200 of N") |

Upgrade unlocks: all competitors, all keywords, the full-library scan, competitor creative/messaging, weekly tracking + alerts, and the ZenABM own-data comparison.

## The core problem

The skill is **distributed as files that run on the user's own machine** (Claude Code / Cowork) using **their own Ad Library token**. That means:

- **Client-side caps are not a security boundary.** The SKILL.md + bundled script will enforce the 3 / 5 / 200 limits and show the upgrade path — this stops normal users — but a technical user can edit the bundled script, or call the API directly with the token, or simply **re-run the skill repeatedly** (3 keywords each run) to accumulate more. A script cannot reliably prevent that.
- **Whoever controls the token controls the real limit.** ZenABM issues the token, so **ZenABM is the only place a hard limit can be enforced.**

## Two layers (defense in depth)

**Layer 1 — the skill (client-side).** Best-effort UX enforcement:
- Refuses >3 keywords, shows only the top 5 competitors + an upgrade teaser, scans at most 200 ads/keyword.
- Every limit is paired with a clear "upgrade with ZenABM" path.
- Purpose: friendly friction + conversion. NOT a hard security boundary.

**Layer 2 — ZenABM backend (the real gate).** Because ZenABM issues the token, enforce the hard limit here. Options, roughly in order of robustness:

| Option | What it is | Pros | Cons |
|---|---|---|---|
| **A. Rate-limit the token** | Cap a free account's token to e.g. N Ad Library calls/day | Simplest; quick to ship | Doesn't hide the method; blunt (a user could still spend the budget however they like) |
| **B. Scoped / short-lived token** | Free accounts get a token scoped to limited calls / short TTL | Better control than raw token | Still a direct-to-LinkedIn token; token refresh UX |
| **C. Proxy the Ad Library through ZenABM** (recommended) | The skill calls a **ZenABM endpoint**, not LinkedIn directly; ZenABM applies the free-tier caps and forwards | Hard enforcement server-side; **also hides the data source/method** (the "secret sauce"); enables usage analytics + in-product upsell; no raw high-access token ever leaves | Requires a ZenABM proxy endpoint; small change to the skill's client (point at ZenABM instead of LinkedIn) |

## Recommendation

- **Ship now:** Layer 1 in the skill (3 / 5 / 200 + upgrade CTAs) — done regardless of the backend decision.
- **For the real gate:** **Option C (proxy)** is the strongest — it enforces limits server-side, hides the method (which you asked to protect), and gives ZenABM usage data + a natural upsell surface. **Option A (rate-limit)** is the fastest interim step if a proxy is too much for v1.
- The skill's API client is written so that switching from "call LinkedIn directly with the pasted token" to "call a ZenABM proxy endpoint" is a **one-line base-URL change** — so we can start direct and move to a proxy later without reworking the skill.

## The one question for the CTO

**Is the token ZenABM hands a free user a raw LinkedIn Ad Library token (full access), or something ZenABM controls (scoped/rate-limited/proxied)?**
- If ZenABM-controlled → we can enforce the hard limit server-side (recommended).
- If raw LinkedIn token → no client-side skill can truly limit it; we should move to a scoped token or the proxy before promoting the free skill widely.

## Status of the working assumption
Per Bilal (pending CTO confirmation): **assume ZenABM will handle server-side enforcement**; the skill implements maximal client-side enforcement in the meantime.

## Residual client-side gaps (2026-07-06 adversarial pass)

The `keyword-competitors` hardening added a cumulative, token-keyed cap (SKILL.md rules + `session_ledger.py`). An adversarial red-team + audit confirmed these residual gaps that **only the server-side gate can close** - they are the "user controls their own machine" class, not the "agent rationalizes past the cap in chat" class that the hardening already closes:

- **Direct API use.** A technical user calls LinkedIn (or the proxy) with the pasted token directly, bypassing the skill entirely.
- **Editing the shipped script.** The user can delete the cap call or raise `DEFAULT_MAX_KEYWORDS`; it runs on their machine.
- **Deleting the ledger.** `~/.zena/ledger.json` is a local file the user owns; wiping it resets the count (same effect as `--reset-session`, which is now gated behind `ZENA_DEV=1`).
- **Ledger deletion / token rotation.** The cap is **per-token lifetime** (no time reset), so it accumulates until the token rotates (~26 days - the natural reset) or the user deletes `~/.zena/ledger.json`. Ledger deletion is the residual here (the user owns the file); only a per-account server-side budget fully closes it.
- **No ledger file locking.** Concurrent/interleaved runs could race; a failed write silently loses the count (best-effort by design).
- **Source concealment.** The persona hides "LinkedIn Ad Library," but the token is a LinkedIn token and the default base URL is `api.linkedin.com`; only the proxy truly hides the method.

Client-side mitigations already shipped: cap-size overrides (`--max-keywords/--max-ads/--top-competitors`) are clamped to the free defaults unless `ZENA_DEV=1`; `--no-ledger`/`--reset-session` are gated behind `ZENA_DEV=1`; keyword normalization folds punctuation/hyphens so trivial rewords cannot buy extra slots; a tokenless run is still capped per run.
