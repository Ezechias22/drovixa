# Phase 8 validation record

Validated on 2026-08-22 before packaging:

- Ruff format/check: passed.
- Strict mypy: passed for 96 backend source files.
- Backend tests: 78 passed; branch-aware coverage 69.05% (required 65%).
- Alembic offline PostgreSQL chain: passed; single head `20260822_0009`.
- Mobile, Web, and Admin TypeScript checks: passed.
- Next.js production builds: passed for 18 public routes and 21 Admin routes.
- Expo public configuration: passed for SDK 57, app version `0.8.0`, and
  app-version runtime policy.
- Android Hermes export: passed (1,941 modules).
- Python dependency audit: no known vulnerabilities after updating
  `cryptography` to the patched 50.x line.
- Web/Admin production dependency audit: no vulnerabilities.
- JSON, Compose YAML, GitHub workflow YAML, and shell syntax parsing: passed.

The production containers and Caddy topology still require runtime validation on
the target Docker host because domains, managed database/Redis connections, and
secrets are owner-specific. Expo/Metro upstream mobile build-tool advisories are
documented in `docs/SECURITY.md`; no force downgrade was applied.
