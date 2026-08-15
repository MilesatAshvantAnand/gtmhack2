# Hackathon credentials

Store shared values only as repository Codespaces secrets. They are available to people with collaborator access who create a Codespace for this repository. Do not copy values into `.env`, source code, issues, pull requests, chat, or GitHub Actions.

| Secret | Create it from | Required restriction |
| --- | --- | --- |
| `ZENABM_HACKATHON_TOKEN` | ZenABM API keys | Separate token; non-production account/data where possible; short expiry; revoke after the hackathon. |
| `HUBSPOT_HACKATHON_TOKEN` | HubSpot test account or dedicated private app | Only scopes and objects used by the demo; no production-wide access. |
| `UNIFYGTM_HACKATHON_API_KEY` | UnifyGTM | Separate project/key; lowest available scope, rate limit, and expiry. |
| `OPENAI_HACKATHON_API_KEY` | Dedicated OpenAI API project, only if the app calls the API | Project budget and rate limits. This is not a Codex login credential. |

GitHub access needs no stored key: use the collaborator invitation and GitHub's built-in `GITHUB_TOKEN` in any future workflow.

## Add a shared secret

1. Create a new hackathon-specific credential with the restrictions above.
2. From a trusted local terminal in this repository, run `./scripts/set-codespaces-secrets.sh`.
3. Each collaborator works in a Codespace created from this repository. Restart an existing Codespace after adding or changing a secret.
4. Delete or revoke all hackathon credentials when the event ends.

Repository Codespaces secrets are deliberately a trust boundary: any collaborator who can run code in the Codespace can use its values. If that is too much access for a credential, do not add it here; expose a narrow server-side operation instead.

An empty GitHub Actions environment named `hackathon` is also present for future approval-gated jobs. Do not put credentials there until `main` requires pull-request review and the environment requires your approval.

An empty GitHub Actions environment named `hackathon` is also present for future approval-gated jobs. Do not put credentials there until `main` requires pull-request review and the environment requires your approval.
