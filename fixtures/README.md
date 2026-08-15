# Fixtures

Keep sanitized, deterministic provider inputs and expected agent outputs here. Fixtures are for local development only: they contain no credentials, live customer records, raw CRM exports, or network-dependent values.

`ashtree/` provides the initial trial-to-value policy cases. Each case has one
input and its expected output; `manifest.json` documents the shared fields and
source labels. The cases cover a verified competitor, incomplete public-ad
coverage, an unverified competitor rejection, and an opted-out trial contact.

All public-ad limitations are represented explicitly. Missing values are
`unknown`, never zero, and every suggested action is evidence-linked and
draft-only.
