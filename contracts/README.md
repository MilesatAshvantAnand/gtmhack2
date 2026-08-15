# Contracts

Versioned JSON Schemas shared by the fixture-first Ashtree workflow live here.
Each insight must include a source identifier and coverage/confidence state; missing
data is `unknown`, never zero.

## Ashtree action boundary

- [`recommended-action.schema.json`](recommended-action.schema.json) defines one
  evidence-bounded action. It requires verified canonical entities, source IDs,
  coverage, confidence, an accountable owner, a measurable success metric, and a
  pending human review. Recommendations are never send instructions.
- [`ashtree-run-envelope.schema.json`](ashtree-run-envelope.schema.json) defines
  one selected-trial workflow run. It records the opt-out/suppression decision,
  permitted draft outputs, and the action recommendations. An opted-out contact
  can only produce a blocked run and cannot produce actions or drafts.

The contracts deliberately exclude raw provider responses and sending fields. Live
provider calls belong only in the owner-approved Codespaces execution boundary.
