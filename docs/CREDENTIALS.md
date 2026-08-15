# Hackathon credentials

Store shared values only as repository Codespaces secrets. They are available to people with collaborator access who create a Codespace for this repository. Do not copy values into `.env`, source code, issues, pull requests, or chat.

| Secret | Create it from | Required restriction |
| --- | --- | --- |
| `ZENABM_HACKATHON_TOKEN` | ZenABM API keys | Dedicated, revocable service token; only the trial-user operations needed by the workflow. |
| `HUBSPOT_HACKATHON_TOKEN` | HubSpot private app or sandbox | Read trial-contact/company properties and create a draft/note/task only; no bulk send or unrelated CRM scopes. |
| `UNIFYGTM_HACKATHON_API_KEY` | UnifyGTM | Separate project/key with the narrowest scope, rate limit, and expiry available. |
| `OPENAI_HACKATHON_API_KEY` | Dedicated OpenAI API project, only if the app calls the API | Project budget and rate limits. This is not a Codex login credential. |

GitHub access needs no stored key: collaborators use their own accounts, and workflows use the built-in `GITHUB_TOKEN`.

## Add a shared secret

1. Create a new hackathon-specific credential with the restrictions above.
2. From a trusted local terminal in this repository, run `./scripts/set-codespaces-secrets.sh` and enter the value at the hidden prompt.
3. Each collaborator works in a Codespace created from this repository. Restart an existing Codespace after adding or changing a secret.
4. Keep production sends disabled. The first live run should create a draft/report only and require a human review before any email or LinkedIn message is sent.
5. Revoke every hackathon credential after the event.

Repository Codespaces secrets are deliberately a trust boundary: any collaborator who can run code in the Codespace can use their values. Do not add a personal GitHub token or an irreplaceable production credential.

An empty GitHub Actions environment named `hackathon` is also present for future approval-gated jobs. Do not put credentials there until `main` requires pull-request review and the environment requires your approval.
