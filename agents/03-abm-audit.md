# ABM audit agent

## Input

An eligible `TrialProfile` whose ZenABM data is connected.

## Work

Use the audit context to calculate only supported performance findings: format-level efficiency, ad-count health, campaign trends, account engagement, and deal influence when CRM data is available.

## Output

An array of `AuditFinding` objects, each with source fields, a coverage state, and a recommended action.

## Rules

- Match the audit skill's metric and benchmark rules.
- Do not grade a metric that does not apply, such as landing-page cost for an ad without a link.
- Do not confuse unavailable data with a zero value.
