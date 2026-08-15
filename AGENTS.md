# Working agreement

This file applies to every contributor and coding agent.

## Goal

Build a real ZenABM trial-to-value workflow: one selected trial receives an evidence-backed growth brief, a prioritized ZenABM next step, and reviewable outreach drafts. Do not build a generic chatbot or an automatic outbound sender.

## Read first

1. `docs/PROJECT_BRIEF.md`
2. `docs/ARCHITECTURE.md`
3. `docs/DELIVERY_PLAN.md`
4. `docs/CREDENTIALS.md`
5. `context/README.md`

## Boundaries

- `context/` is imported reference material. Do not edit it while implementing the workflow. Update it only as a deliberate, reviewed source refresh.
- Put new implementation in `src/`, agent definitions in `agents/`, schemas in `contracts/`, sanitized examples in `fixtures/`, and tests in `tests/`.
- Local development is fixture-only. Live calls run only from a Codespace with dedicated hackathon credentials.
- Never print, commit, or request a credential in chat. Never commit customer data, raw HubSpot data, or generated reports.
- Draft outreach only. Do not call a sending endpoint or automate LinkedIn messaging.

## Evidence rules

- Every insight must carry a source reference and an `unknown`/confidence state where data is incomplete.
- Verify a competitor's canonical LinkedIn company ID before treating a fuzzy advertiser result as a match.
- Public LinkedIn-ad data does not reveal spend, creative text, clicks, or hidden targeting. Do not fabricate them.
- Missing data is unknown, not zero. Treat EU/EEA-only impression visibility as a coverage limitation.

## Change discipline

- Prefer small, focused pull requests.
- Add or update a test with each behavior change.
- Do not add a provider integration before its fixture adapter and contract exist.
- Before finishing, run the relevant tests and `git diff --check`.
