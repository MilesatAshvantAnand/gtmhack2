# Trial intake agent

## Input

HubSpot trial event or a manually selected trial contact/account ID.

## Work

Validate the active trial state, owner/company identity, allowed contact channel, opt-out status, CRM source links, and whether ZenABM data is connected.

## Output

A `TrialProfile` with explicit eligibility, connection state, and source references. Do not enrich unrelated contacts or account records.

## Rules

- An unavailable field is `unknown`.
- An opted-out or suppressed contact stops downstream outreach drafting.
- A trial with no connected data may receive an onboarding-oriented brief, but not a fabricated performance audit.
