# Tests

Local tests are fixture-only: they never read credentials and never contact a
provider. Run either command from the repository root:

```sh
pytest
python -m unittest discover -s tests -p 'test_*.py'
```

`tests/conftest.py` adds the repository root to the import path and exposes
safe JSON fixture helpers. Store deterministic, sanitized JSON under
`fixtures/`; helper discovery is recursive and stable.

The Ashtree harness deliberately skips only while `src/ashtree.py` is absent.
Once that module lands, it must expose `run_fixture(payload)`. The harness will
run it against a checked-in fixture and require a mapping with evidence,
coverage, and draft-only outreach. An existing module with no fixture or no
fixture runner is a failing implementation, not a skipped test.

Test workflow contracts, agent decisions, source-evidence propagation, coverage
limitations, and the draft-only delivery rule.
