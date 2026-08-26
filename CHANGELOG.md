# Changelog

All notable changes to AgentHive are documented here.

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
