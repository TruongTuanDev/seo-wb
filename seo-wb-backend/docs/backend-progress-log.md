# Backend Progress Log

## Phase 0 - 2026-05-18

- Audited the existing FastAPI backend structure, auth flow, store ownership checks, encrypted WB token storage, Gemini integration, SQLAlchemy/Alembic setup, and pytest patterns.
- Confirmed the finance plan document is present at `backend/docs/wb_finance_backend_codex_plan.md` and mapped its intended `docs/*` artifacts into the current backend project layout under `backend/docs`.
- Created `docs/wb-finance-integration-design.md` and initialized `TASKS.md`, `docs/wb-api-field-map.md`, `docs/wb-live-test-report.md`, and `docs/frontend-contract-report.md`.
- Baseline validation: `python -m pytest` -> `18 passed`.

## Phase 1 - 2026-05-18

- Added `WbBaseClient`, category-specific content/common/finance clients, structured WB exceptions, client-side rate limiting, and sanitized API diagnostic logging.
- Added `api_diagnostic_logs` persistence and client test coverage for `429` handling and secret redaction.
- Validation: `python -m pytest` -> `20 passed`.

## Phase 2 - 2026-05-18

- Added `sellers` persistence linked to the existing `stores` ownership model.
- Added `GET /api/v1/wb/health/ping` and `GET /api/v1/wb/seller-info` using the existing encrypted store token flow.
- Live WB diagnostics not run because `WB_LIVE_TESTS` and finance/common/content WB token env variables were not enabled in the shell.
- Validation: `python -m pytest` -> `20 passed`.

## Phase 3 - 2026-05-18

- Added `wb_products` and `wb_product_sync_state`.
- Added product sync service plus query endpoints for synced WB products and sync status.
- Product rows persist searchable fields, sizes, SKUs, and raw WB payload JSONB.
- Validation: `python -m pytest` -> `20 passed`.

## Phase 4 - 2026-05-18

- Added seller finance settings, product finance settings with effective periods, and external costs.
- Added missing-settings query and CSV import/export workflow for product settings.
- Validation includes overlap checks and non-negative money values.
- Validation: `python -m pytest` -> `20 passed`.

## Phase 5 - 2026-05-18

- Added finance detailed-row sync with resume state, `rrdId` upsert behavior, product linking, and raw JSONB preservation.
- Added sync status and raw-row endpoints.
- PostgreSQL migration `20260518_0003_wb_finance_foundation` applied successfully.
- Validation: `python -m pytest` -> `20 passed`.

## Phase 6 - 2026-05-18

- Added Decimal-based summary, timeline, product breakdown, cost breakdown, and tax/profit calculations.
- Dashboard responses now return computed values directly from backend logic instead of expecting frontend money math.
- Validation: `python -m pytest` -> `20 passed`.

## Phase 7 - 2026-05-18

- Added deterministic insights for missing cost settings, negative profit products, and low-margin products.
- Validation: `python -m pytest` -> `20 passed`.

## Phase 8 - 2026-05-18

- Added Gemini finance analysis service and snapshot persistence.
- Missing Gemini key now degrades gracefully to deterministic-only behavior.
- Validation: `python -m pytest` -> `20 passed`.

## Phase 9 - 2026-05-18

- Added sales report list client plus reconciliation endpoint with graceful warning behavior when report-list access is unavailable.
- Validation: `python -m pytest` -> `20 passed`.

## Phase 10 - 2026-05-18

- Added external cost allocation preview and allocation modes for direct, revenue-based, quantity-based, and equal distribution.
- Validation: `python -m pytest` -> `20 passed`.

## Phase 11 - 2026-05-18

- Added CSV export template and CSV import processing for product finance settings.
- Validation: `python -m pytest` -> `20 passed`.

## Phase 12 - 2026-05-18

- Optional acquiring-detail expansion intentionally deferred.
- Current reconciliation uses `acquiringFee` fields already available in the detailed finance report rows, so MVP behavior is not blocked.

## Phase 13 - 2026-05-18

- Added pagination to synced product, product-settings, external-costs, and finance product-breakdown list endpoints.
- Updated frontend contract and finance integration docs.
- No mypy/ruff config exists in this backend, so only the pytest validation path was available.
- Validation: `python -m pytest` -> `20 passed`.

## Live Test Follow-up - 2026-05-18

- Ran direct live WB probe with a manually supplied token through the new backend clients.
- Confirmed successful `200` responses for content/common/finance `ping`, one successful `common seller-info` read, one successful content cards-list read, and one successful finance balance read in diagnostic logs.
- Hit WB server-side `429` cooldown on subsequent `seller-info` and `finance balance` calls with `X-Ratelimit-Retry` near one day.
- Fixed the backend client by persisting endpoint-level cooldown after `429` so immediate repeat calls are blocked locally instead of re-hitting WB.
- Validation after fix: `python -m pytest` -> `21 passed`.

## Stabilization & API Contract Hardening - 2026-05-18

- Audited `WbBaseClient` cooldown behavior and extended local cooldown state to track seller scope, category, host, method, endpoint, retry metadata, and sanitized headers.
- Hardened `429` handling to parse `X-Ratelimit-Retry`, `X-Ratelimit-Reset`, `Retry-After`, `X-Ratelimit-Limit`, and `X-Ratelimit-Remaining`, with safe fallback behavior when headers are missing.
- Added local cooldown inspection for frontend-safe status reporting and ensured no WB token, Gemini key, or other secret is written into diagnostics.
- Added `GET /api/v1/finance/system-status` as a local-state-only readiness endpoint covering API cooldowns, sync timestamps, Gemini configuration, missing finance settings, and unmapped finance rows.
- Audited content product sync cursor behavior and enforced ascending cursor sync payloads for `/content/v2/get/cards/list`.
- Audited finance detailed sync resume logic and preserved `rrdId` pagination, duplicate prevention, JSONB raw rows, and Decimal-only money handling under additional tests.
- Hardened finance schemas and route response models so frontend consumers receive explicit fields, nullability, and pagination metadata instead of inferred contracts.
- Expanded the frontend contract report and added a live-response-shape document based only on already observed live evidence; no new WB call was required for this documentation pass.
- Validation after stabilization: `python -m pytest` -> `25 passed`.
