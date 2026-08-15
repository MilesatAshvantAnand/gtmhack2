# Keyword-Competitors Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Superseded (2026-07-06):** the cap shipped as a **per-token lifetime** cap (`session_window_ms=None`), not the 24h session window this plan describes as the default; see the companion `2026-07-06-keyword-competitors-hardening-design.md` §3.3 and `session_ledger.py`. The test-count predictions below ("177 + new tests") resolved to **197 passing**. This plan is kept as a point-in-time artifact.

**Goal:** Make the `keyword-competitors` skill strict (cumulative free-tier cap), accurate (ranking fix), honest about keyword matching, and consistent about pulling users to ZenABM.

**Architecture:** A new focused module `scripts/session_ledger.py` maintains a token-keyed, session-windowed ledger of keywords scanned; `keyword_scan.py`'s `main()` calls it *before* scanning and refuses over-cap keywords with an upsell (so `run()` stays ledger-agnostic and offline tests are unaffected). A one-line change to `_rank_key` makes share-of-voice primary so limited-visibility advertisers are never buried. SKILL.md is rewritten for rationalization-proof cap rules, agent-layer relevance triage, and a single strong CTA per delivery. A live probe confirms keyword precision cannot be improved server-side.

**Tech Stack:** Python 3.9, pydantic 2, pytest 8. Stdlib only for the new module (`hashlib`, `json`, `os`, `tempfile`, `re`, `dataclasses`). Runs offline; one task needs a live token.

## Global Constraints

- Python **3.9** compatible (no `match`, no `X | Y` unions in annotations — use `Optional[...]`).
- New module is **stdlib-only** (the skill ships standalone; runtime deps are only `requests pydantic python-dotenv`).
- Free-tier caps: **3 keywords total / conversation**, **top 5 competitors / keyword**, **200 ads / keyword**.
- Session window default: **24h** (`SESSION_WINDOW_MS = 24 * 60 * 60 * 1000`).
- **Never store the raw token** — key the ledger by `sha256(token)[:16]`.
- Persona copy rules (SKILL.md): **no emojis**, **hyphens not em-dashes**, never reveal source/model/API.
- Full suite must stay green: `.venv/bin/python -m pytest tests/knowledge_base tests/test_core_client.py tests/test_core_signals.py .claude/skills/keyword-competitors/tests -q` → currently **177 passed**.
- Ledger + ranking live in the skill's `scripts/` (not vendored `core/`), so no re-vendor is needed for them. Re-vendor (`python3 scripts/vendor.py`) only if a `core/` engine module changes.
- All commands run from repo root: `/Users/bilal.ahmad/CC/linkedin-ad-library-usecases`, using `.venv/bin/python`.

---

## File Structure

- **Create** `.claude/skills/keyword-competitors/scripts/session_ledger.py` — token-keyed cumulative cap ledger (stdlib-only, pure/injectable).
- **Create** `.claude/skills/keyword-competitors/tests/test_session_ledger.py` — ledger unit tests.
- **Modify** `.claude/skills/keyword-competitors/scripts/keyword_scan.py` — `main()` enforcement wiring + CLI flags + `format_cap_refusal`; `_rank_key` fix.
- **Modify** `.claude/skills/keyword-competitors/tests/test_keyword_scan.py` — ranking regression test + main()-level cumulative-cap integration test.
- **Create** `scripts/probe_keyword_precision.py` — live precision probe (token-gated) + offline-testable aggregation.
- **Create** `tests/test_probe_keyword_precision.py` — offline unit test of the probe's aggregation with a fake client.
- **Modify** `.claude/skills/keyword-competitors/SKILL.md` — cap rules, relevance triage, CTA overhaul.
- **Modify** `docs/api-knowledge-base/call-patterns.md` — append the precision conclusion (after the live probe).
- **Create** `docs/api-knowledge-base/fixtures/keyword-precision/` — probe fixtures (after the live run).

---

### Task 1: Session ledger module

**Files:**
- Create: `.claude/skills/keyword-competitors/scripts/session_ledger.py`
- Test: `.claude/skills/keyword-competitors/tests/test_session_ledger.py`

**Interfaces:**
- Consumes: nothing (stdlib only).
- Produces:
  - `normalize_keyword(kw: str) -> str`
  - `token_key(token: str) -> str`
  - `default_session_file() -> str`
  - `load_ledger(path: str) -> Dict[str, Any]`
  - `save_ledger(path: str, data: Dict[str, Any]) -> None`
  - `SESSION_WINDOW_MS: int`
  - `@dataclass CapDecision(admitted: List[str], refused: List[str], already_used_count: int, remaining_after: int)`
  - `enforce_cap(requested: Sequence[str], *, token: Optional[str], now_ms: int, max_keywords: int = 3, session_file: Optional[str] = None, session_window_ms: int = SESSION_WINDOW_MS, persist: bool = True) -> CapDecision`

- [ ] **Step 1: Write failing tests for the pure helpers**

Create `.claude/skills/keyword-competitors/tests/test_session_ledger.py`:

```python
"""Unit tests for the free-tier cumulative cap ledger."""
import json
import os

import pytest

# The skill's scripts dir must be importable; conftest/sys.path handles core,
# but session_ledger sits next to keyword_scan.py. Import via its package path.
import importlib.util

SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "scripts"
)


def _load_module():
    path = os.path.join(SCRIPTS_DIR, "session_ledger.py")
    spec = importlib.util.spec_from_file_location("session_ledger", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sl = _load_module()

NOW = 1_700_000_000_000  # fixed epoch ms


def test_normalize_keyword_strips_casefolds_collapses():
    assert sl.normalize_keyword("  Product   Analytics ") == "product analytics"
    assert sl.normalize_keyword("Customer Data Platform") == "customer data platform"


def test_token_key_is_stable_and_not_the_token():
    k1 = sl.token_key("AQU-secrettoken")
    k2 = sl.token_key("AQU-secrettoken")
    assert k1 == k2
    assert "secrettoken" not in k1
    assert len(k1) == 16
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest .claude/skills/keyword-competitors/tests/test_session_ledger.py -q`
Expected: FAIL — `session_ledger.py` does not exist yet (import/exec error).

- [ ] **Step 3: Create the module with helpers**

Create `.claude/skills/keyword-competitors/scripts/session_ledger.py`:

```python
"""Free-tier cumulative cap ledger for the keyword-competitors skill.

Best-effort UX enforcement (NOT a security boundary — see
``docs/free-tier-enforcement.md``): the durable gate is a ZenABM server-side
proxy. This module stops the *accidental and rationalized* bypass where a user
asks for "the other keywords" in a fresh run and gets more than the free tier.

Design:
  * stdlib-only (the skill ships standalone).
  * pure/injectable: ``now_ms`` and ``session_file`` are always passed in;
    ``persist=False`` and dependency-free hashing make it fully testable.
  * token-keyed: the ledger is keyed by ``sha256(token)[:16]`` so switching the
    output directory between runs does NOT reset the count. The raw token is
    never written to disk.
  * session-windowed: an entry older than ``session_window_ms`` (default 24h)
    is treated as a new conversation and its keyword list reset.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

SESSION_WINDOW_MS: int = 24 * 60 * 60 * 1000  # 24h inactivity = new conversation


def normalize_keyword(kw: str) -> str:
    """Trim, collapse internal whitespace, and casefold for dedup/counting."""
    return re.sub(r"\s+", " ", kw.strip()).casefold()


def token_key(token: str) -> str:
    """Stable 16-hex key for a token. Never stores or reveals the token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def default_session_file() -> str:
    """``~/.zena/ledger.json`` when writable, else a temp-dir fallback."""
    base = os.path.join(os.path.expanduser("~"), ".zena")
    try:
        os.makedirs(base, exist_ok=True)
        if os.access(base, os.W_OK):
            return os.path.join(base, "ledger.json")
    except OSError:
        pass
    return os.path.join(tempfile.gettempdir(), "zena-ledger.json")


def load_ledger(path: str) -> Dict[str, Any]:
    """Load the ledger JSON. Missing/corrupt file -> empty dict (never raises)."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_ledger(path: str, data: Dict[str, Any]) -> None:
    """Persist the ledger JSON, creating parent dirs. Swallows write errors."""
    try:
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
    except OSError:
        pass  # best-effort UX; never crash the scan on a ledger write failure


@dataclass
class CapDecision:
    admitted: List[str] = field(default_factory=list)   # keywords to scan (original form)
    refused: List[str] = field(default_factory=list)    # over-cap keywords (original form)
    already_used_count: int = 0                          # distinct kws before this run
    remaining_after: int = 0                             # free slots left after this run
```

- [ ] **Step 4: Run helper tests to verify they pass**

Run: `.venv/bin/python -m pytest .claude/skills/keyword-competitors/tests/test_session_ledger.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Write failing tests for `enforce_cap`**

Append to `test_session_ledger.py`:

```python
def test_enforce_cap_within_limit_admits_all(tmp_path):
    sf = str(tmp_path / "ledger.json")
    d = sl.enforce_cap(
        ["product analytics", "customer data platform"],
        token="tok", now_ms=NOW, session_file=sf,
    )
    assert d.admitted == ["product analytics", "customer data platform"]
    assert d.refused == []
    assert d.remaining_after == 1


def test_enforce_cap_cumulative_across_runs_refuses_overflow(tmp_path):
    sf = str(tmp_path / "ledger.json")
    # Run 1: use all 3.
    d1 = sl.enforce_cap(
        ["product analytics", "customer data platform", "session replay"],
        token="tok", now_ms=NOW, session_file=sf,
    )
    assert d1.admitted == ["product analytics", "customer data platform", "session replay"]
    assert d1.remaining_after == 0
    # Run 2 (the transcript loophole): 2 NEW keywords -> both refused.
    d2 = sl.enforce_cap(
        ["account based marketing", "ecommerce"],
        token="tok", now_ms=NOW + 60_000, session_file=sf,
    )
    assert d2.admitted == []
    assert d2.refused == ["account based marketing", "ecommerce"]
    assert d2.already_used_count == 3


def test_enforce_cap_rescan_of_used_keyword_is_free(tmp_path):
    sf = str(tmp_path / "ledger.json")
    sl.enforce_cap(["product analytics"], token="tok", now_ms=NOW, session_file=sf)
    # Re-scanning the same keyword (any casing) does not consume a slot.
    d = sl.enforce_cap(
        ["Product Analytics", "customer data platform", "session replay", "ecommerce"],
        token="tok", now_ms=NOW + 1000, session_file=sf,
    )
    assert d.admitted == ["Product Analytics", "customer data platform", "session replay"]
    assert d.refused == ["ecommerce"]


def test_enforce_cap_session_window_resets(tmp_path):
    sf = str(tmp_path / "ledger.json")
    sl.enforce_cap(
        ["a keyword", "b keyword", "c keyword"],
        token="tok", now_ms=NOW, session_file=sf,
    )
    # 25h later -> new conversation -> count resets.
    later = NOW + 25 * 60 * 60 * 1000
    d = sl.enforce_cap(["d keyword"], token="tok", now_ms=later, session_file=sf)
    assert d.admitted == ["d keyword"]
    assert d.already_used_count == 0


def test_enforce_cap_different_tokens_are_independent(tmp_path):
    sf = str(tmp_path / "ledger.json")
    sl.enforce_cap(["k1", "k2", "k3"], token="tokA", now_ms=NOW, session_file=sf)
    d = sl.enforce_cap(["k4"], token="tokB", now_ms=NOW, session_file=sf)
    assert d.admitted == ["k4"]


def test_enforce_cap_no_token_admits_all_without_persisting(tmp_path):
    sf = str(tmp_path / "ledger.json")
    d = sl.enforce_cap(["a", "b", "c", "d"], token=None, now_ms=NOW, session_file=sf)
    assert d.admitted == ["a", "b", "c", "d"]
    assert not os.path.exists(sf)  # no token -> no ledger written


def test_enforce_cap_persist_false_does_not_write(tmp_path):
    sf = str(tmp_path / "ledger.json")
    sl.enforce_cap(["a"], token="tok", now_ms=NOW, session_file=sf, persist=False)
    assert not os.path.exists(sf)
```

- [ ] **Step 6: Run to verify the new tests fail**

Run: `.venv/bin/python -m pytest .claude/skills/keyword-competitors/tests/test_session_ledger.py -q`
Expected: FAIL — `enforce_cap` not defined.

- [ ] **Step 7: Implement `enforce_cap`**

Append to `session_ledger.py`:

```python
def enforce_cap(
    requested: Sequence[str],
    *,
    token: Optional[str],
    now_ms: int,
    max_keywords: int = 3,
    session_file: Optional[str] = None,
    session_window_ms: int = SESSION_WINDOW_MS,
    persist: bool = True,
) -> CapDecision:
    """Decide which requested keywords are inside the cumulative free cap.

    Re-scanning an already-recorded keyword is free (does not consume a slot).
    New keywords consume slots until ``max_keywords`` distinct are used across
    the session window. Overflow is refused. With no token the cap cannot be
    keyed, so all are admitted and nothing is written (a scan with no token
    fails later anyway).
    """
    requested = list(requested)
    if not token:
        return CapDecision(
            admitted=requested, refused=[],
            already_used_count=0, remaining_after=max_keywords,
        )

    path = session_file or default_session_file()
    ledger = load_ledger(path)
    key = token_key(token)
    entry = ledger.get(key) or {}
    used: List[str] = list(entry.get("keywords", []))

    # Session window: stale entry -> new conversation -> reset.
    last_seen = entry.get("last_seen_ms")
    if last_seen is not None and now_ms - last_seen > session_window_ms:
        used = []

    used_set = set(used)
    already_used_count = len(used_set)
    slots = max(0, max_keywords - already_used_count)

    admitted: List[str] = []
    refused: List[str] = []
    for kw in requested:
        norm = normalize_keyword(kw)
        if norm in used_set:
            admitted.append(kw)          # re-scan: free
        elif slots > 0:
            admitted.append(kw)
            used_set.add(norm)
            slots -= 1
        else:
            refused.append(kw)

    if persist:
        ledger[key] = {
            "keywords": sorted(used_set),
            "first_seen_ms": entry.get("first_seen_ms", now_ms),
            "last_seen_ms": now_ms,
        }
        save_ledger(path, ledger)

    return CapDecision(
        admitted=admitted,
        refused=refused,
        already_used_count=already_used_count,
        remaining_after=slots,
    )


def reset_session(token: str, session_file: Optional[str] = None) -> None:
    """Clear one token's entry (dev/testing / --reset-session)."""
    if not token:
        return
    path = session_file or default_session_file()
    ledger = load_ledger(path)
    ledger.pop(token_key(token), None)
    save_ledger(path, ledger)
```

- [ ] **Step 8: Run all ledger tests to verify pass**

Run: `.venv/bin/python -m pytest .claude/skills/keyword-competitors/tests/test_session_ledger.py -q`
Expected: PASS (9 tests).

- [ ] **Step 9: Commit**

```bash
git add .claude/skills/keyword-competitors/scripts/session_ledger.py \
        .claude/skills/keyword-competitors/tests/test_session_ledger.py
git commit -m "feat(skill): add token-keyed cumulative cap ledger"
```

---

### Task 2: Wire the cap into `keyword_scan.py` main()

**Files:**
- Modify: `.claude/skills/keyword-competitors/scripts/keyword_scan.py` (`main()`, `build_arg_parser()`, add `format_cap_refusal`)
- Test: `.claude/skills/keyword-competitors/tests/test_keyword_scan.py`

**Interfaces:**
- Consumes: `session_ledger.enforce_cap`, `session_ledger.reset_session`, `CapDecision`.
- Produces: `format_cap_refusal(refused: List[str]) -> str`; new CLI flags `--session-file`, `--no-ledger`, `--reset-session`; `main()` enforces the cumulative cap before scanning.

- [ ] **Step 1: Write a failing main()-level integration test**

Append to `test_keyword_scan.py` (adapt the fake-client construction to match the existing tests in this file — reuse the same stub/fixtures already used there):

```python
def test_main_cumulative_cap_refuses_second_run(tmp_path, monkeypatch, capsys):
    """Two main() runs under one token: run 2's new keywords are refused."""
    import keyword_scan as ks  # imported the same way other tests import it

    # Force a deterministic, offline client (reuse the file's existing stub).
    monkeypatch.setattr(ks, "make_client", lambda: _STUB_CLIENT)  # see file's stub
    monkeypatch.setenv("ZENABM_TOKEN", "tok-integration")
    sf = str(tmp_path / "ledger.json")
    out1 = str(tmp_path / "r1")
    out2 = str(tmp_path / "r2")

    rc1 = ks.main([
        "--keywords", "product analytics, customer data platform, session replay",
        "--out-dir", out1, "--session-file", sf, "--page-sleep", "0",
    ])
    assert rc1 == 0

    rc2 = ks.main([
        "--keywords", "account based marketing, ecommerce",
        "--out-dir", out2, "--session-file", sf, "--page-sleep", "0",
    ])
    out = capsys.readouterr().out
    assert rc2 == 0
    # Nothing new scanned; the refusal names the paywall + ZenABM.
    assert "ZenABM" in out
    assert "account based marketing" in out
    assert not os.path.exists(os.path.join(out2, "report_data.json"))
```

> NOTE for the implementer: open `test_keyword_scan.py` first and mirror its existing offline-client setup (module import style, stub client name, and any `now_ms`/`generated_at` injection). Name the stub reference to match. The other 18 tests must keep passing — they call `run()` directly (no ledger) or should pass `--no-ledger` if they go through `main()`.

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest ".claude/skills/keyword-competitors/tests/test_keyword_scan.py::test_main_cumulative_cap_refuses_second_run" -q`
Expected: FAIL — flags/enforcement not implemented (or report_data.json written in out2).

- [ ] **Step 3: Add `format_cap_refusal` and CLI flags**

In `keyword_scan.py`, add near the other helpers:

```python
def format_cap_refusal(refused: List[str]) -> str:
    """Warm, firm upsell shown when keywords exceed the cumulative free cap."""
    kws = ", ".join(refused)
    return (
        f"NOTE: your free scan covers 3 keywords per conversation, and those are "
        f"used up. I can't add {kws} on the free tier - that is where ZenABM comes "
        f"in: it tracks every theme you care about, always-on, week over week, "
        f"against your own spend and pipeline. Add them at "
        f"https://zenabm.com/book-a-demo (or https://app.zenabm.com/signup)."
    )
```

In `build_arg_parser()`, add (compute mode group):

```python
    p.add_argument("--session-file", default=None,
                   help="Path to the cumulative-cap ledger (default: ~/.zena/ledger.json).")
    p.add_argument("--no-ledger", action="store_true",
                   help="Disable the cumulative free-tier cap (per-run cap only).")
    p.add_argument("--reset-session", action="store_true",
                   help="Clear this token's ledger entry, then continue.")
```

- [ ] **Step 4: Enforce the cap in `main()`**

In `main()`, after args are parsed and keywords parsed, before calling `run()` in compute mode. Add the import at the top of the file:

```python
from session_ledger import enforce_cap, reset_session  # noqa: E402  (skill-local module)
```

> If the file imports its siblings differently (e.g. a `sys.path` shim for `core`), mirror that mechanism for `session_ledger`.

Then in the compute branch of `main()`:

```python
    token = os.environ.get("ZENABM_TOKEN") or os.environ.get("LINKEDIN_ACCESS_TOKEN")

    if args.reset_session and token:
        reset_session(token, session_file=args.session_file)

    if args.no_ledger:
        keywords_to_scan = keywords
    else:
        decision = enforce_cap(
            keywords,
            token=token,
            now_ms=now_ms,
            max_keywords=args.max_keywords,
            session_file=args.session_file,
        )
        if decision.refused:
            print(format_cap_refusal(decision.refused), file=sys.stdout)
            print(file=sys.stdout)
        if not decision.admitted:
            return 0  # entire run over cap; upsell already printed
        keywords_to_scan = decision.admitted

    # ... existing: run(keywords_to_scan, client=..., ...)
```

> Replace the existing `run(keywords, ...)` call with `run(keywords_to_scan, ...)`. Ensure `now_ms` is the same value `main()` already computes/injects for `run()`.

- [ ] **Step 5: Keep the other tests offline-safe**

If any existing test drives `main()` (not `run()`), add `--no-ledger` to its argv so it doesn't touch `~/.zena`. Tests that call `run()` directly need no change.

Run: `.venv/bin/python -m pytest .claude/skills/keyword-competitors/tests -q`
Expected: PASS — the new integration test + all prior skill tests.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest tests/knowledge_base tests/test_core_client.py tests/test_core_signals.py .claude/skills/keyword-competitors/tests -q`
Expected: PASS (was 177; now 177 + new ledger/integration tests).

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/keyword-competitors/scripts/keyword_scan.py \
        .claude/skills/keyword-competitors/tests/test_keyword_scan.py
git commit -m "feat(skill): enforce cumulative keyword cap in main() with upsell"
```

---

### Task 3: Ranking fix — share-of-voice first

**Files:**
- Modify: `.claude/skills/keyword-competitors/scripts/keyword_scan.py` (`_rank_key`, ~line 500)
- Test: `.claude/skills/keyword-competitors/tests/test_keyword_scan.py`

**Interfaces:**
- Produces: `_rank_key(c: Dict[str, Any]) -> tuple` sorting by `(n_ads_on_keyword, linkedin_maturity_score, active_tiebreak)` descending, where `active_tiebreak = {True: 2, None: 1, False: 0}`.

- [ ] **Step 1: Write the failing regression test**

Append to `test_keyword_scan.py`:

```python
def test_rank_key_volume_beats_visibility():
    """A high-volume limited-visibility advertiser outranks a low-volume active one.

    This is the Multiply/UserGems bug: 45 ads with coverage 'none'
    (is_currently_advertising=None) must rank ABOVE 2 ads that are confirmed active.
    """
    import keyword_scan as ks
    loud_unknown = {
        "n_ads_on_keyword": 45,
        "linkedin_maturity_score": 3,
        "is_currently_advertising": None,   # limited visibility
    }
    quiet_active = {
        "n_ads_on_keyword": 2,
        "linkedin_maturity_score": 3,
        "is_currently_advertising": True,
    }
    ranked = sorted([quiet_active, loud_unknown], key=ks._rank_key, reverse=True)
    assert ranked[0] is loud_unknown


def test_rank_key_active_is_only_a_tiebreaker():
    """Equal volume + maturity: confirmed-active wins the tiebreak."""
    import keyword_scan as ks
    a = {"n_ads_on_keyword": 10, "linkedin_maturity_score": 5, "is_currently_advertising": True}
    b = {"n_ads_on_keyword": 10, "linkedin_maturity_score": 5, "is_currently_advertising": None}
    ranked = sorted([b, a], key=ks._rank_key, reverse=True)
    assert ranked[0] is a
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest ".claude/skills/keyword-competitors/tests/test_keyword_scan.py::test_rank_key_volume_beats_visibility" -q`
Expected: FAIL — current key sorts by active-status first, so `quiet_active` wins.

- [ ] **Step 3: Fix `_rank_key`**

Replace the function body (~line 500):

```python
def _rank_key(c: Dict[str, Any]) -> tuple:
    """Rank by share of voice first; visibility never buries volume.

    Sort DESCENDING on:
      1. n_ads_on_keyword     - share of voice (robust across visibility tiers)
      2. linkedin_maturity_score
      3. active_tiebreak      - {True: 2, None: 1, False: 0}; low-weight tiebreak only

    Fixes the bug where a limited-visibility advertiser (is_currently_advertising
    is None) was buried below a confirmed-active advertiser with far fewer ads.
    """
    active_tiebreak = {True: 2, None: 1, False: 0}[c["is_currently_advertising"]]
    return (c["n_ads_on_keyword"], c["linkedin_maturity_score"], active_tiebreak)
```

> Confirm every caller sorts with `reverse=True` (descending). If a caller relied on the old ascending/first-key behavior, update it so top competitors are the highest-volume. Search: `grep -n "_rank_key" .claude/skills/keyword-competitors/scripts/keyword_scan.py`.

- [ ] **Step 4: Run to verify pass + fix any disturbed assertions**

Run: `.venv/bin/python -m pytest .claude/skills/keyword-competitors/tests -q`
Expected: PASS. If an existing test asserted a specific top-5 order that changes, update it to the new (correct) volume-first order and confirm the change is intentional.

- [ ] **Step 5: Verify visibility is surfaced for shown competitors**

Read `build_competitor` / `_signal_bits` / `print_digest` and confirm each shown competitor exposes `impression_data_coverage` (or an equivalent visibility label) in both the digest and `report_data.json`, so Zena can narrate visibility on first mention. If missing, add `coverage` to the competitor dict and to the digest line. Run the suite again:

Run: `.venv/bin/python -m pytest .claude/skills/keyword-competitors/tests -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/keyword-competitors/scripts/keyword_scan.py \
        .claude/skills/keyword-competitors/tests/test_keyword_scan.py
git commit -m "fix(skill): rank by share-of-voice so visibility never buries volume"
```

---

### Task 4: Keyword-precision live probe + offline test

**Files:**
- Create: `scripts/probe_keyword_precision.py`
- Test: `tests/test_probe_keyword_precision.py`

**Interfaces:**
- Consumes: `core.client.LinkedInAdLibraryClient` (live) or any object with `.search(keyword=..., start=0, count=1)` returning an object with `.paging.total`.
- Produces: `probe_forms(base_keyword: str) -> List[str]` (the query variants to try); `run_probe(client, base_keyword: str) -> List[Dict[str, Any]]` returning `[{"form": str, "query": str, "total": int}, ...]`.

- [ ] **Step 1: Write the failing offline test (fake client)**

Create `tests/test_probe_keyword_precision.py`:

```python
"""Offline test of the keyword-precision probe's query construction + aggregation."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import probe_keyword_precision as pk  # noqa: E402


class _FakePaging:
    def __init__(self, total): self.total = total


class _FakeResp:
    def __init__(self, total): self.paging = _FakePaging(total)


class _FakeClient:
    """Returns a total that depends on the query, to prove each form is sent."""
    def __init__(self): self.queries = []
    def search(self, keyword=None, start=0, count=1):
        self.queries.append(keyword)
        return _FakeResp(len(keyword) if keyword else 0)


def test_probe_forms_include_quoted_and_multiword_variants():
    forms = pk.probe_forms("product analytics")
    joined = " ".join(forms)
    assert '"product analytics"' in joined      # quoted-phrase variant
    assert "product analytics" in joined         # baseline


def test_run_probe_records_total_per_form():
    client = _FakeClient()
    rows = pk.run_probe(client, "product analytics")
    assert all(set(r) == {"form", "query", "total"} for r in rows)
    assert len(rows) == len(pk.probe_forms("product analytics"))
    assert len(client.queries) == len(rows)  # one call per form
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_probe_keyword_precision.py -q`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the probe**

Create `scripts/probe_keyword_precision.py`:

```python
"""Probe whether the Ad Library keyword param supports any precision operator.

Live usage (needs a valid token in ZENABM_TOKEN):
    ZENABM_TOKEN=... python3 scripts/probe_keyword_precision.py "product analytics"

Records paging.total for each query form. Interpretation: if the quoted /
boolean / punctuation forms return the same order of magnitude as the plain
form, the API does no phrase/precision matching (confirming call-patterns.md
§4c). Saves nothing by itself; capture responses as fixtures separately.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List


def probe_forms(base_keyword: str) -> List[str]:
    """Query variants to compare for precision behavior."""
    b = base_keyword.strip()
    return [
        b,                          # baseline
        f'"{b}"',                   # quoted phrase (re-confirm quotes ignored)
        b.replace(" ", " +"),       # '+'-prefixed tokens
        b.replace(" ", " AND "),    # explicit AND
        b.replace(" ", ", "),       # comma-separated
        b.upper(),                  # casing
        f" {b} ",                   # surrounding whitespace
    ]


def run_probe(client: Any, base_keyword: str) -> List[Dict[str, Any]]:
    """Return [{form, query, total}] for each variant (one search per form)."""
    labels = [
        "baseline", "quoted", "plus_tokens", "explicit_and",
        "comma_sep", "uppercase", "surrounding_ws",
    ]
    rows: List[Dict[str, Any]] = []
    for label, query in zip(labels, probe_forms(base_keyword)):
        resp = client.search(keyword=query, start=0, count=1)
        rows.append({"form": label, "query": query, "total": resp.paging.total})
    return rows


def main(argv: List[str]) -> int:
    if not argv:
        print('usage: probe_keyword_precision.py "<keyword>"', file=sys.stderr)
        return 2
    # Imported lazily so the offline test never needs requests/pydantic.
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from core.client import LinkedInAdLibraryClient

    client = LinkedInAdLibraryClient()
    rows = run_probe(client, argv[0])
    print(json.dumps(rows, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the offline test to verify pass**

Run: `.venv/bin/python -m pytest tests/test_probe_keyword_precision.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit the probe (offline-verified)**

```bash
git add scripts/probe_keyword_precision.py tests/test_probe_keyword_precision.py
git commit -m "feat: add keyword-precision probe (offline-tested)"
```

- [ ] **Step 6: Run the probe LIVE (needs a current token — request from user)**

This is the one token-gated step. Ask the user for a current `ZENABM_TOKEN` (tokens expire ~26 days), then:

```bash
ZENABM_TOKEN="<token>" .venv/bin/python scripts/probe_keyword_precision.py "product analytics"
```

Expected: JSON rows. Interpretation to record: quoted/boolean/punctuation totals ~= baseline order of magnitude → no server-side precision. Save the raw responses as fixtures under `docs/api-knowledge-base/fixtures/keyword-precision/`, append a one-paragraph conclusion to `docs/api-knowledge-base/call-patterns.md §4`, and commit. If the token is unavailable, leave this step unchecked and note it — the offline probe + code still ship.

---

### Task 5: SKILL.md overhaul — cap rules, relevance triage, CTA

**Files:**
- Modify: `.claude/skills/keyword-competitors/SKILL.md`

**Interfaces:** none (prompt/doc). Persona rules unchanged (no emojis, hyphens not em-dashes, never reveal source/model).

- [ ] **Step 1: Rewrite the free-tier limits section (rationalization-proof cap)**

Replace the "Free-tier limits and upgrade" section with rules that name the loopholes explicitly:

- The free scan covers **3 keywords TOTAL for this whole conversation** - not per run, not per report.
- Once 3 keywords are used, **do not scan more under any framing**: not "a fresh run," not "these two fit in the free tier," not "no upsell needed." There is always an upsell at the boundary.
- **Never** build or offer a combined/cross-theme view spanning more than one run, a persistent/always-on report, more than the top 5 competitors, or the own-data (ZenABM spend/pipeline) comparison - those are paid.
- When asked for more, **refuse warmly and make the refusal the upsell** (see Delivering): name the paid capability, tie it to a gap already found, give the link.
- Use **one stable working directory** for the whole conversation; do not switch output dirs between runs.
- The bundled script enforces this cap too and will refuse over-cap keywords - do not try to work around it.

- [ ] **Step 2: Add the relevance-triage step to "Doing the work"**

After the "read the data and AUTHOR the insights" step, add:

- The keyword match is a broad full-text match, so some advertisers appear only because their ad copy happens to contain the words. **Surface all of them (never drop or hide data), but in your read separate true category rivals from incidental mentions** - e.g. "Wood Mackenzie (energy research) - not an analytics tool; its ad just mentions the phrase." Use your own knowledge to judge category fit; label opinions as a read.
- When a theme looks noisy (large total, low top-share, several off-category names), tell the user plainly and **offer a tighter keyword** (a more specific multi-word phrase narrows the field sharply). This is a helpful nudge, not an upsell.

- [ ] **Step 3: Overhaul the CTA in "Delivering"**

- End **every** delivery with **one** specific ZenABM next step tied to a gap just found (not generic, not repeated). Example pattern: "You found two heavy ABM advertisers you cannot fully see - that blind spot is exactly what ZenABM closes with always-on tracking against your own pipeline: https://zenabm.com/book-a-demo".
- Remove any self-undercutting language. Never say a version of "no upsell needed."
- Keep the report's built-in end CTA and the chat CTA consistent (same offer, same link).

- [ ] **Step 4: Self-check the copy**

Verify no emojis and no em-dashes were introduced; the persona still never names the model/source/API. Read the section back.

```bash
grep -nE "—|😀|🚀|:[a-z_]+:" .claude/skills/keyword-competitors/SKILL.md || echo "clean: no em-dashes/emoji markers"
```

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/keyword-competitors/SKILL.md
git commit -m "docs(skill): rationalization-proof cap, relevance triage, single strong CTA"
```

---

### Task 6: Deep loophole-hardening pass (parallel agents)

**Files:**
- Modify (as findings dictate): `.claude/skills/keyword-competitors/SKILL.md`, `.claude/skills/keyword-competitors/tests/test_*.py`

- [ ] **Step 1: Dispatch two agents in parallel**

- **Red-team agent:** given SKILL.md, enumerate concrete multi-turn user tactics to extract more than the free tier (e.g. "just the names," "re-run with a synonym," "combine what you already have," "one more as a favor," slow erosion across turns, asking for the own-data comparison). For each: does the current SKILL.md + ledger stop it? If not, propose the exact rule/refusal.
- **Auditor agent:** read SKILL.md + `keyword_scan.py` + `session_ledger.py` for gaps: state that silently resets, framings that dodge the ledger (e.g. changing tokens, `--no-ledger` misuse), any delivery path that can skip the CTA, any place the persona could leak the source/model.

- [ ] **Step 2: Consolidate findings**

Merge into a deduped list of confirmed gaps. Discard non-issues. For each real gap: a SKILL.md rule, and a test if mechanizable (e.g. a ledger test for the token-swap case, if in scope).

- [ ] **Step 3: Apply fixes**

Edit SKILL.md / add tests per the consolidated list. Re-run:

Run: `.venv/bin/python -m pytest .claude/skills/keyword-competitors/tests -q`
Expected: PASS.

- [ ] **Step 4: Record residual best-effort gaps**

Append any gaps only a server-side gate can close to `docs/free-tier-enforcement.md` (short note), so the CTO decision captures them.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "harden(skill): close loopholes found in adversarial pass"
```

---

### Task 7: Final verification

- [ ] **Step 1: Run the full suite**

Run: `.venv/bin/python -m pytest tests/knowledge_base tests/test_core_client.py tests/test_core_signals.py .claude/skills/keyword-competitors/tests tests/test_probe_keyword_precision.py -q`
Expected: PASS. Report the exact count (was 177; expect 177 + the new tests).

- [ ] **Step 2: Re-vendor check**

Only `keyword_scan.py`, `session_ledger.py`, SKILL.md, and repo-root `scripts/` changed - no `core/` engine module changed, so no re-vendor is required. Confirm:

```bash
git diff --name-only HEAD~7..HEAD | grep -E "^core/" || echo "no core/ changes - no re-vendor needed"
```

If any `core/` file did change: `python3 scripts/vendor.py` then re-run the suite.

- [ ] **Step 3: Sanity smoke (offline, --no-ledger)**

```bash
.venv/bin/python .claude/skills/keyword-competitors/scripts/keyword_scan.py --help
```
Expected: help shows `--session-file`, `--no-ledger`, `--reset-session`.

- [ ] **Step 4: Update HANDOVER.md / CLAUDE.md open items**

Note the hardening (cumulative cap, ranking fix, precision conclusion, CTA) and that the live-probe step / server-side gate remain the token-dependent / CTO-pending items.

```bash
git add HANDOVER.md CLAUDE.md
git commit -m "docs: record keyword-competitors hardening in handover"
```

---

## Self-Review

**1. Spec coverage:**
- §3 free-tier enforcement (behavioral + backstop) → Tasks 1, 2, 5.
- §4 ranking fix → Task 3.
- §5 keyword-match honesty (live probe + triage) → Tasks 4, 5.
- §6 CTA overhaul → Task 5.
- §7 deep loophole pass → Task 6.
- §8 testing → every task's TDD steps + Task 7.
- §9 out of scope → not implemented (correct).
- §10 success criteria → criteria 1 (Tasks 2+5), 2 (Task 5), 3 (Task 3), 4 (Tasks 4+5), 5 (Task 5), 6 (Tasks 1-3, 7). Covered.

**2. Placeholder scan:** No TBD/TODO. Task 2's test carries a NOTE to mirror the existing file's stub setup (unavoidable — the implementer must read the real stub name); the test body and wiring code are complete otherwise.

**3. Type consistency:** `enforce_cap`/`CapDecision`/`token_key`/`normalize_keyword`/`reset_session` signatures match between Task 1 (definition) and Task 2 (use). `_rank_key` returns a 3-tuple used with `reverse=True` consistently. `run_probe`/`probe_forms` signatures match between Task 4 definition and test.

---

## Execution Handoff

See the top-of-plan REQUIRED SUB-SKILL note.
