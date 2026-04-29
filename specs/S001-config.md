# S001 - Project Skeleton + Config + Env Loading

**Phase:** 1 | **Depends on:** none | **Priority:** P0

## What
Create the base config module using pydantic-settings. Loads all environment variables needed by the pipeline (database, OpenAI, email, app settings) with validation and sensible defaults for local dev.

## Files
- Create: `src/oykos/config.py`
- Create: `tests/unit/test_config.py`

## Tests
- `test_config_loads_from_env` - config loads all required fields from env vars
- `test_config_defaults` - optional fields have correct defaults (model names, log level)
- `test_config_missing_required_raises` - missing DATABASE_URL or OPENAI_API_KEY raises ValidationError
- `test_config_recipient_parsing` - RECIPIENT_EMAILS string parsed to list correctly

## Acceptance
- [ ] Tests pass
- [ ] `vibe-check.ps1` green
- [ ] No hardcoded secrets/config
- [ ] Config is importable as `from oykos.config import settings`
