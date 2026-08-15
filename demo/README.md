# GTMHack2 interactive demo

This is a zero-dependency, fixture-backed presentation layer for the First-Week ABM Rescue Brief. It intentionally contains no credentials, provider calls, customer data, enrichment writes, campaign writes, or sending code.

## Run it

From the repository root:

```bash
python3 -m http.server 8000 --directory demo
```

Open `http://localhost:8000`.

## Presenter path

1. Select **Northstar Analytics** and run the plan.
2. Narrate the five agent handoffs.
3. In the finished brief, click **Preview Unify handoff**. Explain that the production boundary asks Unify for a bounded account brief or DataTable; the fixture proves the UX without accessing a real workspace.
4. Highlight the evidence labels, partial-coverage limitation, and human-reviewable email.
5. Reset and show **Harbor Studio** to demonstrate that an opt-out fails closed before enrichment or drafting.

## Unify production boundary

The application must call a server-side adapter, never a browser-held API key. The adapter receives a verified `TrialProfile`, requests only an account brief or limited DataTable from Unify, records source references, and returns a bounded evidence packet. It must not create a Sequence or enroll contacts. A production adapter belongs in `src/` and runs only from the repository's Codespaces credential boundary.
