# Contributing

Create a branch, keep the change focused, and open a pull request. Ask for review from `@bilalahmad20` for changes to context, credentials, or workflow configuration.

Develop against `fixtures/`. A contributor may work on agent prompts, contracts, adapters, reports, and tests without live provider access. Run live calls only in the shared Codespace after the implementation is reviewed.

Before opening a pull request:

1. Run the relevant tests.
2. Run `git diff --check`.
3. Confirm no credential, customer data, raw provider response, or generated report is staged.
4. State how the change preserves the evidence and draft-only rules in `AGENTS.md`.
