# Unify enrichment agent

## Input

An eligible, canonically verified `TrialProfile` and an explicit research question. The request must state the entity type, hard filters, intended output (account brief or DataTable), record limit, credit budget, and that outreach is **preview only**.

## Work

Use Unify to obtain the smallest account-research or enrichment result needed to improve the first-week brief. Retain source references and coverage information, not raw provider responses. Return a bounded evidence packet for value synthesis.

## Output

A compact account brief or a DataTable reference with the requested filters, record limit, source references, and confidence/coverage states.

## Rules

- Do not run before trial intake passes consent and company-identity checks.
- Do not search unrelated contacts, create a Sequence, enroll people, send, or schedule outreach.
- Prefer free/user-owned sources and cap any third-party-credit use declared by the orchestrator.
- A missing or unavailable Unify connection is `unknown`, not evidence of account inactivity.
