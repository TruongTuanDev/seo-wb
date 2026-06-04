# Finance Frontend Implementation Report

## Status

Implementation complete. Build passes. Lint passes.

## Commands Run

```
npm run lint   → exit 0, 0 errors
npm run build  → exit 0, 11/11 pages compiled
```

## Pages Created

| Route | File | Description |
|---|---|---|
| `/finance` | `app/(dashboard)/finance/page.tsx` | Main finance dashboard |
| `/finance/settings` | `app/(dashboard)/finance/settings/page.tsx` | Seller finance settings |
| `/finance/product-settings` | `app/(dashboard)/finance/product-settings/page.tsx` | Product cost settings |
| `/finance/external-costs` | `app/(dashboard)/finance/external-costs/page.tsx` | External costs management |

## Components Created

| Component | File | Purpose |
|---|---|---|
| `SyncStatusBadge` | `components/finance/SyncStatusBadge.tsx` | Status pill: idle/running/completed/failed/rate_limited |
| `CooldownAlert` | `components/finance/CooldownAlert.tsx` | WB cooldown banner with retry countdown |
| `FinanceSystemStatusCard` | `components/finance/FinanceSystemStatusCard.tsx` | API status block + sync times + Gemini flag |
| `FinanceSummaryCards` | `components/finance/FinanceSummaryCards.tsx` | 10 metric cards from summary endpoint |
| `FinanceTimelineChart` | `components/finance/FinanceTimelineChart.tsx` | SVG bar chart for `forPay` per bucket |
| `FinanceCostBreakdownSection` | `components/finance/FinanceCostBreakdownSection.tsx` | WB costs / COGS / external split with progress bars |
| `FinanceInsightsPanel` | `components/finance/FinanceInsightsPanel.tsx` | Deterministic backend insights with level-based styling |
| `GeminiAnalysisPanel` | `components/finance/GeminiAnalysisPanel.tsx` | Gemini analyze button + snapshot history; disabled state when not configured |
| `FinanceDateRangeFilter` | `components/finance/FinanceDateRangeFilter.tsx` | Date from/to inputs + group_by day/week/month/year toggle |
| `SellerFinanceSettingsForm` | `components/finance/SellerFinanceSettingsForm.tsx` | react-hook-form form for seller-level defaults |
| `ProductFinanceSettingsTable` | `components/finance/ProductFinanceSettingsTable.tsx` | Table with edit modal, CSV import/export |
| `ExternalCostsTable` | `components/finance/ExternalCostsTable.tsx` | CRUD table for external costs with confirm delete |
| `ProductBreakdownTable` | `components/finance/ProductBreakdownTable.tsx` | Paginated product finance breakdown, client-side search, negative profit highlight |

## Library Files Created

| File | Purpose |
|---|---|
| `lib/types/finance.ts` | All finance TypeScript interfaces |
| `lib/finance-api.ts` | Typed API client wrapping `lib/api.ts` |
| `lib/finance-utils.ts` | `formatMoney`, `formatPercent`, `formatDate`, `formatRetryAfter`, helpers |

## Navigation Changes

- `app/(dashboard)/DashboardClientLayout.tsx` updated:
  - Added `Finance` dropdown nav item (desktop)
  - Added Finance Dashboard link to mobile nav bar
  - `switchStore` now preserves current finance sub-path when switching stores

## API Client Methods Implemented

All methods from `frontend-contract-report.md`:
- `getSystemStatus`
- `triggerProductSync` / `getProductSyncStatus`
- `getWbProducts`
- `triggerFinanceSync` / `getFinanceSyncStatus`
- `getSummary` / `getTimeline` / `getProductBreakdown` / `getCostBreakdown` / `getInsights` / `getReconciliation`
- `getSellerSettings` / `updateSellerSettings`
- `getProductSettings` / `getProductSettingsById` / `updateProductSetting`
- `getMissingSettings`
- `getExportTemplateUrl` / `importSettings`
- `getExternalCosts` / `createExternalCost` / `updateExternalCost` / `deleteExternalCost`
- `getExternalCostAllocationPreview`
- `analyzeWithGemini` / `getGeminiSnapshots`

## Environment Variables Used

- `NEXT_PUBLIC_API_URL` — backend base URL (inherited from existing `lib/api.ts`)
- `NEXT_PUBLIC_CSRF_COOKIE_NAME` — CSRF cookie name (inherited)

No new environment variables introduced.

## UI Features Implemented

- Loading skeletons on all cards and tables
- Empty states for all data-absent scenarios
- Cooldown alerts on dashboard with `retryAfterSeconds` countdown
- Missing settings banner with link to product settings page
- Unmapped rows warning banner
- Sync buttons disabled during cooldown and while sync is running
- Conservative 5-second polling during active sync (stops when complete)
- Negative profit row highlighting in product table
- Missing cost settings row flagging
- Gemini disabled state (not an error)
- CSV import with row-level error display
- Store-aware routing (`store_id` propagated through all finance routes)

## Known Limitations

1. Timeline chart only shows `forPay` — matches backend contract (single metric per bucket)
2. No chart library installed; SVG bar chart is custom — no zoom/pan
3. Product breakdown table uses client-side search filter on current page results only (server-side search not in contract)
4. Reconciliation endpoint is implemented in `financeApi` but not surfaced as a UI page (not in required pages list)
5. External cost allocation preview (`preview-allocation`) is in API client but not shown in UI; out of scope for this phase
6. Product sync `full` toggle not shown in UI; uses `full=false` by default as per contract guidance

## Backend Contract Assumptions

- All money fields are strings, never floats
- Request bodies use snake_case; responses use camelCase
- `store_id` required on all finance endpoints as query param
- `perPage` defaults to 50 in product breakdown, 50 in product settings/external costs
- Timeline `group_by` accepts: day, week, month, year

## What Remains for Manual QA

1. Verify all endpoints respond correctly with a live backend + WB token
2. Test CSV import with a real export template
3. Test Gemini analysis with a configured Gemini key
4. Verify cooldown display with a real 429 response
5. Verify store switching preserves `store_id` on finance sub-pages
6. Test mobile layout at 375px and 768px viewports
7. Test reconciliation endpoint separately if needed
