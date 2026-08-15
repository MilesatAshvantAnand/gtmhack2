"""Shared core library (Layer 2). Consumed by all sub-projects and skills.

Modules (import the submodule you need directly — the package stays import-light
so `core.schema` / `core.signals` don't drag in `requests`):
  core.schema  — pydantic response models (auto-validated against captured fixtures)
  core.signals — inferable signal derivations (pure, tier-aware; see inferable-signals.md)
  core.client  — LinkedIn Ad Library API client (drops the rejected countries/adType params)

Not yet built:
  core.zenabm  — ZenABM MCP client wrapper (needed by skills 1 & 2)
"""
