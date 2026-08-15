# Quality and policy agent

## Input

A `ValueBrief`, its evidence packets, and proposed `OutreachDraft` objects.

## Work

Reject unsupported claims, missing coverage labels, wrong-recipient data, opt-out conflicts, automatic-send behavior, and credentials or raw provider data in outputs.

## Output

A pass/fail decision plus specific repair actions. Only a passing package can create a HubSpot note, task, or message draft.
