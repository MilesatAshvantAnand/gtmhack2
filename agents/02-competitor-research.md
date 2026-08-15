# Competitor research agent

## Input

A verified trial-company identity and a list of candidate competitor names, domains, or LinkedIn company URLs.

## Work

Resolve each candidate to a canonical LinkedIn company identity, then use the competitor-intelligence context to create a public-ad evidence packet.

## Output

A `CompetitorBrief` containing verified competitors, coverage limits, observed activity signals, and evidence references.

## Rules

- A fuzzy advertiser match is only a candidate. Verify the canonical company ID before presenting it as a competitor.
- Do not report public-ad impressions as spend, or missing visibility as inactivity.
- Do not claim ad creative, clicks, landing pages, or hidden targeting details that the source does not provide.
