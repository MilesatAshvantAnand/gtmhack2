# Orchestrator

## Input

One `TrialProfile` identifier and an explicit run mode: `fixture` or `live`.

## Sequence

1. Run trial intake.
2. Stop on ineligible, opted-out, or unconnected states.
3. Run account and competitor research in parallel only after a company identity is available.
4. Run the ABM audit when the user's ZenABM data is connected.
5. Send the evidence packets to value synthesis.
6. Send the resulting brief to outreach drafting and quality/policy review.
7. Persist a report plus HubSpot draft/note only when quality passes.

## Output

One `ValueBrief`, zero or more `OutreachDraft` objects, and a run status. A stopped run must explain why without exposing sensitive data.

## Stop conditions

- The trial is not active.
- Marketing suppression or an opt-out applies.
- The company identity cannot be verified.
- Required evidence is missing and no transparent partial brief is possible.
