# Shared context

The safe, reusable source from the two supplied projects is now versioned in this repository. Collaborators can inspect and reuse it without access to its original repositories or any API credential.

| Imported package | Source | Contents |
| --- | --- | --- |
| `context/linkedin-ad-library-usecases/` | `https://github.com/bilalahmad20/linkedin-ad-library-usecases` at `3fa01a9726da61a20fab6d95e11456b4a21590ee` | API knowledge base and fixtures, ZenABM API client/core, and competitor-intelligence skill. |
| `context/zenabm-linkedin-abm-audit/` | Local `LinkedIn Ad Library API` / `ZenABM Skills Test Emilia/linkedin-abm-audit` | Trial-user ABM audit skill, benchmarks, data playbook, flags, and report assets. |

Excluded deliberately: `.env` files, virtual environments, generated reports/installers, macOS metadata, legacy contact-data tooling, and source files known to use the pre-audit LinkedIn client. The source knowledge base is authoritative for LinkedIn Ad Library constraints and inference rules.

When updating a context package, copy only the relevant tracked files, record the source revision here, and run a credential-file check before committing.
