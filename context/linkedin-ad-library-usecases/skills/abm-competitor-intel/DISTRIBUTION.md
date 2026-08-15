# Distributing the keyword-competitors skill

How to share, install, and run this skill - in Claude Code, in Claude Cowork, in Codex or another coding agent, or straight from the command line.

## 1. What this skill is

`keyword-competitors` is a guided, agent-driven skill (persona "Zena by ZenABM") that finds who else is advertising on a set of B2B keywords, ranks the field, and produces one combined, self-contained HTML report the user can share. It is portable because it is just two things: `SKILL.md` (the persona and the full guided conversation, i.e. the instructions an agent follows) plus a self-contained Python script (`scripts/keyword_scan.py`) that ships its own vendored engine. There is no external service to install and no build step - drop the folder somewhere an agent can read it and run commands, and it works.

## 2. What to share

Share the whole `keyword-competitors/` folder. It is self-contained. Inside it:

- `SKILL.md` - the Zena persona and the start-to-finish guided conversation (the agent's instructions).
- `scripts/keyword_scan.py` - the entry script (compute mode + render mode).
- `scripts/session_ledger.py` - the token-keyed free-tier cap ledger.
- `scripts/core/` - a vendored copy of the engine (`__init__.py`, `schema.py`, `client.py`, `signals.py`, `report_html.py`) so the skill runs standalone.
- `references/onboarding.md` - the first-time setup walkthrough (signup, connect LinkedIn, paste token).
- `examples/example-combined-report.html` - a sample of the finished report.
- `tests/` - `test_keyword_scan.py` and `test_session_ledger.py`.

Runtime dependencies are just three Python packages (`requests`, `pydantic`, `python-dotenv`) on Python 3.9+.

## 3. What NOT to share

- **Never include a saved token.** Do not ship a `.env` file, and do not paste a token into any file. The token is per-user and per-session; it is provided at runtime via the `ZENABM_TOKEN` environment variable (legacy `LINKEDIN_ACCESS_TOKEN` is also accepted).
- **Do not ship the ledger.** `~/.zena/ledger.json` is local machine state (the free-tier cap counter), not part of the skill. It is created per-user at runtime and should never travel with the folder.

## 4. Install in Claude Code

The folder is auto-discovered by Claude Code. Two locations:

- **Project-scoped:** drop `keyword-competitors/` into a project's `.claude/skills/` directory. It is available inside that project.
- **Global:** drop `keyword-competitors/` into `~/.claude/skills/`. It is available in every project.

Or `git clone` the repo and run `claude` from it - the skill under `.claude/skills/` is picked up automatically.

**How the user triggers it:** they just ask in chat, e.g. "who else is advertising on product analytics?" or "size up my competitors' paid social on customer data platforms." Zena then walks them through setup (ZenABM signup, connect LinkedIn, paste the access token in chat) and produces the report. The user never opens a terminal.

## 5. Share via Claude Cowork

Cowork takes an uploaded zip of the skill folder. From the repo:

```bash
cd .claude/skills && zip -r keyword-competitors.zip keyword-competitors
```

Then upload `keyword-competitors.zip` in Cowork. (The repo also carries `.claude/.claude-plugin/plugin.json`, which lets the whole repo be installed as a plugin via a marketplace, if you prefer distributing the repo rather than the single skill.)

## 6. Use in Codex or another coding agent

Be clear-eyed here: Codex and most other coding agents do not have a native "skills" system like Claude's - there is no skills folder and no auto-discovery. This skill is fundamentally a `SKILL.md` (instructions + persona) plus a self-contained Python script, so it still works anywhere an agent can read a file and run a command. Two steps:

1. **Point the agent at `SKILL.md`** as its instructions or system prompt, so it follows the same guided Zena flow (onboarding, up to 3 keywords, run the scan, author the insights, deliver the report).
2. **Let it run the bundled script** the same way Claude does - `scripts/keyword_scan.py` in compute mode, then render mode (see section 7).

If you would rather not drive it through an agent at all, just run the script by hand - it is self-contained. The exact commands are below.

## 7. Running the bundled script directly

Install the deps once:

```bash
python3 -m pip install requests pydantic python-dotenv
```

(If this errors with "externally-managed-environment" / PEP 668, retry with `--user` or use a virtualenv.)

Make the token available - either export it or put it in a `.env` next to where you run:

```bash
export ZENABM_TOKEN="<your-token>"
```

**Compute mode** - scan the keywords, write `report_data.json`, render a draft `report.html`, and print a DIGEST:

```bash
python3 scripts/keyword_scan.py --keywords "product analytics, customer data platform" --out-dir /tmp/zena-run
```

**Render mode** - after the insight fields in `report_data.json` are written, bake them into the final report:

```bash
python3 scripts/keyword_scan.py --render /tmp/zena-run/report_data.json --out /tmp/zena-run/report.html
```

Notes:
- Write outputs to a writable working directory (e.g. `/tmp/zena-run`), never into the installed skill folder, which may be read-only.
- Render mode is stdlib-only; it does not need `requests` or `pydantic`. The compute path does.
- An optional `ZENABM_API_BASE_URL` can be set if ZenABM gave you one; otherwise leave it unset (it defaults to the public Ad Library base URL). The legacy `LINKEDIN_API_BASE_URL` is also accepted.

## 8. Updating the skill after engine changes (repo maintainers only)

> This section applies only if you have the full repo. If you received just the skill folder, skip it - `vendor.py` lives at the **repo root**, not inside the skill, and `docs/free-tier-enforcement.md` (referenced elsewhere here) is a repo-internal design doc not shipped with the skill.

`scripts/core/` is a **vendored copy** of the engine that lives in the repo's top-level `core/`. If you change any engine module (`schema.py`, `client.py`, `signals.py`, `report_html.py`, or `core/__init__.py`), re-sync the copy from the repo root:

```bash
python3 scripts/vendor.py
```

This copies `core/{__init__,schema,client,signals,report_html}.py` into every skill's `scripts/core/`. It is only needed when those engine modules changed - it is a copy step, not a transform. Skill-specific files like `keyword_scan.py` and `session_ledger.py` are not vendored (they live directly in `scripts/`), so edits to them need no re-vendor.

## 9. Free-tier and token notes

- **The cap:** the free tier is 3 keywords cumulative per token (for the life of the token, not per run), the top 5 competitors per keyword, and the top 200 ads scanned per keyword. Re-scanning a keyword already counted is free; new keywords consume slots until 3 are used.
- **Where the ledger lives:** the cap is tracked in a token-keyed ledger at `~/.zena/ledger.json` (falling back to a temp-dir file if `~/.zena` is not writable). It is keyed by a hash of the token; the raw token is never written to disk.
- **How to reset for testing:** delete `~/.zena/ledger.json`, or rotate to a fresh token - tokens naturally expire in about 26 days, which is the natural reset. Because the ledger is token-keyed, changing the output directory does NOT reset the count.
- **`ZENA_DEV=1` is maintainer-only.** Without it, `--no-ledger` and `--reset-session` are ignored, and the cap-size overrides (`--max-keywords`, `--max-ads`, `--top-competitors`) are clamped down to the free defaults - so a chat user cannot raise or disable the free tier. (`--session-file` is honored for testing, but pointing it at a fresh path just resets the count the same way deleting `~/.zena/ledger.json` would - a documented residual in `docs/free-tier-enforcement.md`; the skill instructs the agent never to pass it.) Do not set `ZENA_DEV=1` when distributing or running for real users.
- **Token expiry:** tokens expire after roughly 26 days. If a run fails on authorization, regenerate the token in ZenABM and re-paste - there is no automatic refresh.
