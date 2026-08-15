# External References

Curated inventory of resources we can leverage or learn from. Divided into two lanes: **LinkedIn Ad Library specific** and **general Claude Code / project leverage**.

Last updated: 2026-07-03

---

## Lane A — LinkedIn Ad Library specific

### Official Anthropic-side (LinkedIn's own material)

- **[LinkedIn Engineering — Enhancing transparency with LinkedIn's Ad Library](https://www.linkedin.com/blog/engineering/trust-and-safety/enhancing-transparency-with-linkedins-ad-library)** — Official statement of what the Ad Library exposes: ad preview, company, payer, first/last impression dates, total impressions, per-country impressions, targeting parameters with inclusion/exclusion status, landing page URL, creative. For restricted ads: advertiser name, payer name, and ad preview are withheld.

- **LinkedIn Ad Library API docs (referenced in current `docs/LINKEDIN_API_OFFICIAL.md`)** — Endpoint spec, parameters, sample request. Note: LinkedIn's own developer docs are inconsistent (they mention `dateRange` params that don't actually work). Our knowledge base supersedes the LinkedIn docs where they conflict with tested behavior.

- **Microsoft Learn — LinkedIn Marketing API** — Different product (paid Ad Manager integration). Only relevant as a comparison point: has `fields` parameter for metric selection and returns clicks + spend that Ad Library does NOT.

### Third-party wrappers / scrapers to know about

- **[linkedin-developers/linkedin-api-python-client](https://github.com/linkedin-developers/linkedin-api-python-client)** — Official LinkedIn Python client, beta. Thin wrapper focused on auth/headers/protocol. Could replace our hand-rolled `_make_request` in `linkedin_client.py` but doesn't add Ad-Library-specific value. **Verdict:** monitor, don't adopt yet.

- **[wukimidaire/linkedin_ads_scraper](https://github.com/wukimidaire/linkedin_ads_scraper)** — Playwright-based scraper (browser automation, not API). Captures: age demographics, gender targeting, seniority. **Notable** because it scrapes fields the official API doesn't expose (age + gender explicit values, not just "targeting parameter present"). Could be a fallback for enrichment when the API surface is insufficient. **Verdict:** revisit for enrich_ads.py Phase 2.

- **SearchAPI + SociaVault** — Paid API wrappers that scrape and normalize Ad Library data. Useful competitive reference — check their marketing pages for "fields we return" to spot inferable signals we haven't thought of. **Verdict:** ~1hr scan during M3 audit.

### Data-side references

- **DSA (Digital Services Act)** compliance — the *reason* impression data exists at all. EU/EEA targeting → LinkedIn required to expose impressions. US-only ads → no impression data. This is the root cause of the `impression_data_coverage = none` case, not a bug.

---

## Lane B — General Claude Code / project leverage

### Anthropic official

- **[anthropics/skills](https://github.com/anthropics/skills)** — Official Agent Skills format. **`SKILL.md` with YAML frontmatter** is the shape our sub-project 2 skills must conform to. Direct impact: any skill we publish should follow this schema so it's installable via `/plugin install skill-name@bilal-linkedin`.

- **[anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official)** — The marketplace format. If we publish a plugin bundle (multiple skills together), the `marketplace.json` shape from this repo is what to mirror.

- **[anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins)** — Plugins for knowledge workers (not just devs). Closer to the persona a "get everything on top 5 competitors" skill targets. Study the tone and packaging.

- **[anthropics/claude-code](https://github.com/anthropics/claude-code)** — Claude Code itself. The `plugins/README.md` documents the plugin manifest structure we'll need.

### Community skill collections (mine for inspiration)

- **[obra/superpowers](https://github.com/obra/superpowers)** (40.9k stars) — **Already installed on this machine.** Structures the SDLC as brainstorm → plan → TDD → review. Aligns with our per-sub-project process. Model the sub-project workflow on this rather than inventing our own.

- **[ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills)** (13k stars) — Curated skills list. Browse for prior art before designing our own.

- **[rohitg00/awesome-claude-code-toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit)** — 135 agents, 35 skills, 42 commands, 176+ plugins. Massive superset. Use as a "has anyone already built this?" lookup.

- **[mingrath/awesome-claude-skills](https://github.com/mingrath/awesome-claude-skills)** and **[BehiSecc/awesome-claude-skills](https://github.com/BehiSecc/awesome-claude-skills)** — Additional curated lists.

- **[glebis/claude-skills](https://github.com/glebis/claude-skills)** — Personal collection. Useful as a "what does a single-author skill portfolio look like" example, since sub-project 2 is exactly that.

### Python project structure / QA best practices

- **[startdataengineering.com — Integration tests for Python data pipelines](https://www.startdataengineering.com/post/python-datapipeline-integration-test/)** — Fixture patterns for pytest with SQLite. Direct pattern for `tests/knowledge_base/` where fixtures = captured API responses.

- **pytest fixture pattern for API responses** — Standard practice: capture real responses to JSON, version them, load via fixture, assert schema. This is what M5 (regression suite) implements.

- **Consider `pydantic` models** for response validation as a stretch goal — auto-generates schema docs, catches drift. TBD in M3.

---

## Actively considered but rejected

- **Building our own auth client** — LinkedIn's OAuth is stable enough that requests+dotenv is fine. No need to add `oauthlib` or LinkedIn's official client unless we hit refresh-token pain.

- **Switching from SQLite to Postgres/Supabase now** — Overkill for a single-user pipeline. Revisit if we scale beyond 40k companies or want multi-writer.

- **Playwright-based scraping for the primary path** — Slower, more brittle, more expensive. Keep API as primary; browser scraping stays as fallback for enrich_ads.py only.
