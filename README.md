# ZenABM trial-to-value GTM workflow

An AI-agent workflow that turns a new ZenABM free trial into a useful, evidence-backed growth brief before asking for a paid conversion.

The workflow combines:

- the trial user's permitted ZenABM performance data;
- public competitor-ad intelligence;
- permitted HubSpot trial context; and
- optional UnifyGTM enrichment.

It creates a report, a HubSpot note/task, and email/LinkedIn-message drafts. It never auto-sends outreach.

## Start here

1. Read [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md).
2. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/DELIVERY_PLAN.md](docs/DELIVERY_PLAN.md).
3. Follow [AGENTS.md](AGENTS.md), whether you are using Codex, Claude, Cursor, Copilot, or working manually.
4. Treat `context/` as read-only reference material. Build new workflow code in `src/`, with sanitized examples in `fixtures/` and tests in `tests/`.

## Repository map

```text
context/       Imported ZenABM product knowledge, skills, core code, and fixtures
docs/          Product brief, architecture, delivery plan, and credentials policy
agents/        New workflow agent definitions and prompts
contracts/     Stable schemas shared between agents and integrations
fixtures/      Sanitized inputs and expected outputs for local development
src/           New workflow, integrations, and report generation code
tests/         Tests for all new workflow behavior
.github/       Collaboration templates and review ownership
```

## Working together

- Make changes on a branch and open a pull request, even though this repository's GitHub plan cannot enforce review.
- Keep live provider calls in a Codespace with dedicated hackathon credentials. Local development uses fixtures.
- Never commit credentials, customer data, raw provider responses, or generated reports.
- Keep the first version draft-only. A human reviews every customer-facing message before sending.
