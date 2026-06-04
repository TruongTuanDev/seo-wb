# TASKS

## Wildberries Finance Reporting Service

- [x] Phase 0: audit existing backend structure and create integration docs
- [x] Phase 1: add WB base clients, category rate limiting, and diagnostic logging
- [x] Phase 2: add seller diagnostics and seller sync
- [x] Phase 3: add WB product sync and product query endpoints
- [x] Phase 4: add seller/product finance settings and external costs
- [x] Phase 5: add finance report sync with JSONB raw row storage
- [x] Phase 6: add finance aggregation and Decimal-based profit calculations
- [x] Phase 7: add deterministic finance insights and alerts
- [x] Phase 8: add Gemini finance analysis snapshots
- [x] Phase 9: add finance report list reconciliation
- [x] Phase 10: add advanced external cost allocation
- [x] Phase 11: add product cost import/export workflow
- [ ] Phase 12: add optional acquiring detail reconciliation
- [x] Phase 13: add pagination, indexing review, and final frontend contract

## Stabilization & API Contract Hardening

- [x] Audit WB 429 cooldown parsing, local cooldown persistence, and safe diagnostics
- [x] Add database-backed finance system status endpoint for frontend readiness checks
- [x] Audit product sync cursor behavior and add resume/upsert coverage
- [x] Audit finance sync `rrdId` resume behavior and add multi-page/429 coverage
- [x] Audit Decimal, date-range, and timezone handling across finance flows
- [x] Harden finance response schemas and pagination metadata
- [x] Expand frontend contract documentation for Antigravity handoff
- [x] Document observed live WB response shapes from existing reports only
- [x] Re-run backend test suite after stabilization changes

## Frontend Implementation by Antigravity

- [ ] Build finance dashboard and reporting UI against `docs/frontend-contract-report.md`
- [ ] Build product sync and synced product management UI
- [ ] Build seller finance settings UI
- [ ] Build product finance settings and CSV import/export UI
- [ ] Build external costs management UI
- [ ] Build finance sync controls and reconciliation UI
- [ ] Build Gemini analysis and snapshot UI
- [ ] Handle cooldown, missing-settings, and unmapped-row states exactly as documented

## Notes

- Product sync must complete before finance profit analytics.
- All money calculations must use `Decimal`.
- Preserve raw WB responses in JSONB.
- Append progress after each phase to `docs/backend-progress-log.md`.
- Append every live WB test to `docs/wb-live-test-report.md`.
- Backend finance implementation and stabilization are complete for frontend handoff.
- Phase 12 remains optional and was intentionally left out of the MVP implementation because detailed sales reports already expose acquiring fee fields used by the current reconciliation flow.
