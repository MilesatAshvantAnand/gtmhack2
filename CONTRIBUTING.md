# Contributing

GitHub Issues are the source of truth for open work. Create or claim an issue before starting, keep the change focused, and open a pull request that closes the issue. Ask for review from `@bilalahmad20` for changes to context, credentials, or workflow configuration.

Use one branch per issue, named `issue/<number>-<short-description>`. Work from a normal checkout for one task. Use a separate Git worktree only when you have two independent issues active at once; never work on the same branch from two worktrees. Before starting or opening a pull request, fetch `origin/main` and incorporate its current changes.

Do not commit directly to `main` after this setup phase. Keep `main` deployable and use it only for merged pull requests.

Develop against `fixtures/`. A contributor may work on agent prompts, contracts, adapters, reports, and tests without live provider access. Run live calls only in the shared Codespace after the implementation is reviewed.

Before opening a pull request:

1. Run the relevant tests.
2. Run `git diff --check`.
3. Confirm no credential, customer data, raw provider response, or generated report is staged.
4. State how the change preserves the evidence and draft-only rules in `AGENTS.md`.
