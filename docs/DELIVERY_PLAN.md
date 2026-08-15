# Hackathon delivery plan

## Demo promise

Select one new ZenABM trial. The workflow produces a branded "first-week growth brief": a short account snapshot, a competitor-ad read, an own-performance finding where data exists, three prioritized actions, and a reviewable outreach draft that points back to ZenABM.

## Build order

1. **Shared context — complete.** Import the audited competitor and ABM-audit source with no credentials.
2. **Contracts and fixtures.** Define `TrialProfile`, `CompetitorBrief`, `AuditFinding`, `ValueBrief`, and `OutreachDraft`. Add sanitized fixtures for a connected trial, an unconnected trial, incomplete public-ad coverage, and an opted-out contact.
3. **Fixture-first agents.** Build the intake, research, audit, synthesis, copy, and quality agents against fixtures. The output must include evidence IDs and confidence/unknown fields.
4. **Owner-only live runner.** Run the same pipeline from the owner's local environment or a separate private runner repository. It takes a HubSpot contact or ZenABM account ID, executes the same pipeline, and writes a report plus HubSpot draft/note.
5. **Live proof.** Run one owner-approved trial account. Validate every number against its source, then collect user feedback on whether the brief makes the paid value clear.

## Division of work

| Workstream | Collaborator-safe work | Owner-only work |
| --- | --- | --- |
| Context and reasoning | Agent prompts, contracts, fixtures, evaluation cases, report UX | None |
| Integration adapters | Interfaces and mocked responses | API implementation and secret wiring |
| Workflow | Orchestration logic and tests | Owner-only live-run execution |
| Outreach | Draft templates, policy checks, report copy | Review and any send action |

## Success checks

- The brief contains at least one real own-data or competitor-data insight, or transparently says why it cannot.
- Every recommendation points to a source field or explicitly carries an `unknown`/directional label.
- The workflow produces a draft, not a send.
- A collaborator can run all tests with fixtures and no credentials.
- A live run requires owner approval and creates no raw-secret or raw-provider-data artifact in Git.
