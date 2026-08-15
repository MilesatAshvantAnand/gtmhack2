# Contracts

Versioned JSON Schemas shared by the fixture-first Ashtree workflow live here.
Each insight must include a source identifier and coverage/confidence state; missing
data is `unknown`, never zero.

## Artifact flow

```text
Evidence references
  -> TrialProfile
  -> CompetitorBrief + AuditFinding[]
  -> ValueBrief
  -> OutreachDraft[]
  -> AshtreeRunEnvelope
```

Every artifact stores evidence IDs rather than raw provider responses. Coverage
and confidence remain explicit at each claim boundary.

- [`evidence.schema.json`](evidence.schema.json) defines the extracted,
  field-level source record.
- [`trial-profile.schema.json`](trial-profile.schema.json) defines eligibility
  for one explicitly selected trial.
- [`competitor-brief.schema.json`](competitor-brief.schema.json) permits at most
  three canonically verified competitors and bounded public-ad activity fields.
- [`audit-finding.schema.json`](audit-finding.schema.json) defines one
  evidence-linked finding and requires limitations when coverage is unknown.
- [`value-brief.schema.json`](value-brief.schema.json) defines the concise,
  evidence-linked first-week brief.
- [`outreach-draft.schema.json`](outreach-draft.schema.json) can represent only
  drafts requiring human review; it has no send, schedule, or launch state.

## Fixture and run boundaries

- [`ashtree-fixture-input.schema.json`](ashtree-fixture-input.schema.json) and
  [`ashtree-policy-outcome.schema.json`](ashtree-policy-outcome.schema.json)
  validate every sanitized policy input and expected output.

- [`recommended-action.schema.json`](recommended-action.schema.json) defines one
  evidence-bounded action. It requires verified canonical entities, source IDs,
  coverage, confidence, an accountable owner, a measurable success metric, and a
  pending human review. Recommendations are never send instructions.
- [`ashtree-run-envelope.schema.json`](ashtree-run-envelope.schema.json) defines
  one selected-trial workflow run. It records the opt-out/suppression decision,
  permitted draft outputs, and the action recommendations. An opted-out contact
  can only produce a blocked run and cannot produce actions or drafts. Inactive,
  unknown, and suppressed eligibility cannot produce a review-ready run.

The contracts deliberately exclude raw provider responses and sending fields. Live
provider calls belong only in the owner-approved Codespaces execution boundary.
