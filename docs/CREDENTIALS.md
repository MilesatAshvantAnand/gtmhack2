# Live credentials

This shared repository is deliberately credential-free. Collaborators get source context and fixtures, not live provider credentials. Do not create repository, Codespaces, or Actions secrets here. Do not place values in `.env`, source code, issues, pull requests, or chat.

The owner-only boundary cannot be enforced in this private repository on the current GitHub plan: required environment reviewers and private-repository branch protection are unavailable. A GitHub secret would therefore be usable by a collaborator who changes a workflow. Keep all live execution in either the repository owner's local environment or a second private runner repository to which the collaborator has no access.

| Secret | Create it from | Required restriction |
| --- | --- | --- |
| `ZENABM_ADMIN_TOKEN` | ZenABM API keys | Dedicated, revocable service token; only the trial-user read operations needed by the workflow. |
| `HUBSPOT_TRIALS_TOKEN` | HubSpot private app or sandbox | Read trial-contact/company properties and create a draft/note/task only; no bulk send or unrelated CRM scopes. |
| `UNIFYGTM_API_KEY` | UnifyGTM | Separate project/key with the narrowest scope, rate limit, and expiry available. |
| `OPENAI_API_KEY` | Dedicated OpenAI API project, only if the app calls the API | Project budget and rate limits. This is not a Codex login credential. |

GitHub access needs no stored key: collaborators use their own accounts, and workflows use the built-in `GITHUB_TOKEN`.

## Owner-only execution

1. Create a new hackathon-specific credential with the restrictions above.
2. Store it only in the owner's local secret store/environment or in an owner-only deployment secret store.
3. Keep production sends disabled. The first live run should create a draft/report only and require a human review before any email or LinkedIn message is sent.
4. Revoke every hackathon credential after the event.

If a hosted workflow is needed after the hackathon, create a separate private runner repository or upgrade the GitHub plan and enforce both protected `main` reviews and required environment approval before adding a secret.

An empty GitHub Actions environment named `hackathon` is also present for future approval-gated jobs. Do not put credentials there until `main` requires pull-request review and the environment requires your approval.
