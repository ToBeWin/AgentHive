# Changelog

All notable changes to AgentHive are documented here.

## [0.3.0-alpha.2] - 2026-08-26

### Fixed

- Raised the locked `cryptography` floor to the first version containing the current security fixes and refreshed `pypdf`.
- Added repository-level Gitleaks configuration and removed secret-like values from test fixtures so public CI can scan the latest commit cleanly.
- Made runtime evidence verification include the diagnostic classifier used by the Agent runtime.
- Corrected Dependabot Docker directories to match the repository's actual Dockerfile locations.
- Hardened the local release workflow and aligned all application, container and widget version markers.

### Verification

- Backend: 926 tests passed, with 58 subtests passed.
- Local Gitleaks scan: no leaks found.
- Runtime evidence verification: passed.

## [0.3.0-alpha.1] - 2026-08-26

### Added

- Enterprise AI management console with role-oriented workspaces for employees, administrators and operations.
- Agent catalog, installation gates, Agent instances, knowledge-base bindings and runtime diagnostics.
- LLM provider/model governance, routing policies, budget controls, cost ledger, circuit breaker and audit evidence.
- PostgreSQL + pgvector knowledge persistence with MinIO storage and replaceable RAGFlow integration.
- Unified Channel Gateway contracts for WeCom, DingTalk, Feishu, Web Widget, REST API and Webhook flows.
- Media generation gateway contracts for image/video jobs, reference assets, asynchronous workers and output archives.
- Private deployment scripts for installation, upgrades, diagnostics, backup/restore and License checks.
- React/TypeScript frontend, FastAPI backend, Docker Compose examples, CodeQL, Dependabot and Gitleaks CI coverage.
- README product guide, system screenshots, MIT license and vulnerability reporting policy.

### Verification

- Backend: 926 tests passed, with 58 subtests passed.
- Frontend: 430 tests passed; TypeScript, Biome, workflow verifiers and production build passed.
- Delivery scripts and development/production/infra Compose configuration passed local verification.

### Known limitations

- This is an alpha release, not a production GA certification.
- Live provider credentials, customer-specific TLS, capacity, disaster recovery and acceptance evidence must be completed per deployment.
- Some official Agent modules and media providers are catalogued ahead of their full customer-facing runtime integration.
