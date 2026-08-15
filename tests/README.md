# Tests

Local tests are fixture-only: they never read credentials and never contact a
provider. Install the development-only validator and run either command from
the repository root:

```sh
python3 -m pip install -r requirements-dev.txt
pytest
python -m unittest discover -s tests -p 'test_*.py'
```

`tests/conftest.py` adds the repository root to the import path and exposes
safe JSON fixture helpers. Store deterministic, sanitized JSON under
`fixtures/`; helper discovery is recursive and stable.

The Ashtree integration test skips only while the fixture adapter or contracts
have not landed. Once present, it compares every policy result to its expected
fixture and validates every public run envelope against Draft 2020-12 JSON
Schema. An existing integration with a mismatch is a test failure.

Test workflow contracts, agent decisions, source-evidence propagation, coverage
limitations, and the draft-only delivery rule.
