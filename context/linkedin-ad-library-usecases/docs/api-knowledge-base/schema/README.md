# Schema — machine-readable response spec

Auto-generated from `core/schema.py` (pydantic v2 models).

## Regenerate

```bash
python3 -c "
import json, sys
from pathlib import Path
sys.path.insert(0, '.')
from core.schema import AdLibraryResponse, ApiError, AdElement, AdStatistics, TargetingFacet
OUT = Path('docs/api-knowledge-base/schema')
for name, model in [('ad_library_response', AdLibraryResponse), ('api_error', ApiError),
                     ('ad_element', AdElement), ('ad_statistics', AdStatistics), ('targeting_facet', TargetingFacet)]:
    s = model.model_json_schema()
    s['\$schema'] = 'https://json-schema.org/draft/2020-12/schema'
    s['\$id'] = f'https://linkedin-ad-library-api.local/schema/{name}.json'
    (OUT / f'{name}.json').write_text(json.dumps(s, indent=2, sort_keys=True))
"
```

## Files

| File | Root model | Use |
|---|---|---|
| `ad_library_response.json` | `AdLibraryResponse` | Full 200 response envelope: `{elements, paging}` |
| `api_error.json` | `ApiError` | 4xx error envelope: `{status, code, message, errorDetails}` |
| `ad_element.json` | `AdElement` | Single element from `elements[]` |
| `ad_statistics.json` | `AdStatistics` | DSA-conditional impression data |
| `targeting_facet.json` | `TargetingFacet` | One entry in `details.adTargeting[]` |

## Runtime use (Python skills)

```python
from core.schema import AdLibraryResponse
import requests

resp = requests.get(url, headers=..., params=...).json()
validated = AdLibraryResponse.model_validate(resp)   # raises ValidationError if drift
for ad in validated.elements:
    if ad.details.adStatistics:
        # tier S signals safe
        ...
```

## Regression tests

The pytest suite in `tests/knowledge_base/` validates every captured fixture against these schemas. Any LinkedIn API change that breaks the shape fails the suite → forces a re-audit of `response-fields.md` before merging code that depends on it.

```bash
python3 -m pytest tests/knowledge_base/ -v
```

Currently 114 tests, all passing (2026-07-03).
