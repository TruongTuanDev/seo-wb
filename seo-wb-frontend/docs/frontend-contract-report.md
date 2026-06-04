# Frontend Contract Report

## Scope

This document describes the existing backend contract for the Wildberries Finance Reporting Service inside the current FastAPI backend. It is intended for the frontend implementation phase only. It does not replace backend code or existing auth/store modules.

All endpoints below reuse the existing authenticated user flow and existing store ownership checks. Every finance or WB endpoint requires a valid `store_id` that belongs to the current user.

## Base API Prefix

- Finance routes documented here use base prefix: `/api/v1`
- Wildberries helper routes documented here use base prefix: `/api/v1`
- Examples in this file always show the full backend route path under `/api/v1`

## Auth Requirements

- Authentication is unchanged from the existing backend.
- Frontend must send the same bearer token or authenticated session already used by the project.
- Backend resolves the current user first, then validates `store_id` ownership.
- Frontend must not send WB tokens or Gemini keys directly to finance endpoints.

## Shop and Seller Selection Flow

- Frontend must first reuse the existing app store selection flow.
- Every request in this finance module must include `store_id` as a query parameter.
- Backend derives the seller internally from the existing store record.
- Frontend must not send `seller_id` directly.
- If the selected store does not belong to the current user, backend rejects the request through the existing ownership guard.

## Common Error Shape

Application errors use the shared backend error structure:

```json
{
  "error": {
    "code": "string_code",
    "message": "Human readable message",
    "details": {}
  }
}
```

FastAPI validation errors can still return the framework validation shape for malformed query/body values. Frontend should treat HTTP `422` as user-fixable input errors.

Validation error example:

```json
{
  "detail": [
    {
      "type": "date_from_parsing",
      "loc": ["query", "date_from"],
      "msg": "Input should be a valid date",
      "input": "2026/05/01"
    }
  ]
}
```

Application-level validation error example:

```json
{
  "error": {
    "code": "invalid_date_range",
    "message": "date_to must be greater than or equal to date_from.",
    "details": {}
  }
}
```

## Cooldown Response Example

WB cooldowns now surface as explicit backend errors. Example:

```json
{
  "error": {
    "code": "wildberries_rate_limited",
    "message": "Wildberries API endpoint is still in cooldown.",
    "details": {
      "retry_after_seconds": 86360.0,
      "category": "finance",
      "host": "seller-analytics-api.wildberries.ru",
      "endpoint": "/api/v1/account/balance",
      "source": "local_cooldown"
    }
  }
}
```

Frontend handling recommendation:

- Show endpoint or service temporarily unavailable.
- Show retry countdown using `retry_after_seconds`.
- Do not auto-retry rapidly.
- Refresh `GET /api/v1/finance/system-status` before retrying sync buttons.

## Recommended Loading States

- Use skeleton/loading for all dashboard cards while summary loads.
- Treat sync actions as long-running buttons with disabled state.
- Refresh system status before enabling product sync or finance sync controls.
- Keep table pagination state local to each view.
- When a sync endpoint returns `status=running` from follow-up status checks, keep sync buttons disabled and poll status conservatively.

## Recommended Empty States

- No synced products: prompt user to run WB product sync first.
- No finance rows in selected date range: prompt user to run finance sync for that period.
- Missing finance settings: show count and link to product settings import/edit flow.
- No AI snapshots: show that analysis has not been generated yet.
- Unmapped finance rows: show warning state and link to synced products and cost-setting cleanup.

## Recommended Error States

- `wildberries_rate_limited`: show cooldown-specific UI with retry seconds.
- `product_not_found`, `external_cost_not_found`: show stale UI item warning and refresh list.
- `invalid_date_range`: keep the current page open and highlight date inputs.
- `unsupported_import_file`: prompt user to upload CSV only.
- Validation `422`: highlight exact form fields when possible.
- `failed` or `rate_limited` sync status: keep the current filters, show the last backend error, and offer manual retry only after status refresh.

## System Status Flow

### `GET /api/v1/finance/system-status?store_id={id}`

Purpose:

- Read local backend state only.
- Do not call WB live.
- Give the frontend a single source of readiness truth before syncs and dashboard loads.

Response:

```json
{
  "contentApi": {
    "available": true,
    "inCooldown": false,
    "activeCooldownCount": 0,
    "cooldowns": []
  },
  "financeApi": {
    "available": false,
    "inCooldown": true,
    "activeCooldownCount": 1,
    "cooldowns": [
      {
        "sellerId": 12,
        "category": "finance",
        "host": "seller-analytics-api.wildberries.ru",
        "method": "GET",
        "endpoint": "/api/v1/account/balance",
        "retryAfterSeconds": 86360.0,
        "source": "server_429",
        "headers": {
          "x-ratelimit-limit": "1",
          "x-ratelimit-remaining": "0",
          "x-ratelimit-retry": "86360",
          "x-ratelimit-reset": null
        }
      }
    ]
  },
  "commonApi": {
    "available": true,
    "inCooldown": false,
    "activeCooldownCount": 0,
    "cooldowns": []
  },
  "sellerInfoApi": {
    "available": true,
    "inCooldown": false,
    "activeCooldownCount": 0,
    "cooldowns": []
  },
  "activeCooldowns": [],
  "lastSuccessfulProductSyncAt": "2026-05-18T08:13:00+00:00",
  "lastSuccessfulFinanceSyncAt": "2026-05-18T08:25:00+00:00",
  "lastFailedSyncAt": "2026-05-18T08:40:00+00:00",
  "lastFailedSyncError": "Wildberries API rate limit reached. retry_after_seconds=86360.0",
  "geminiConfigured": true,
  "hasProductsMissingFinanceSettings": true,
  "missingFinanceSettingsCount": 4,
  "hasUnmappedFinanceRows": false,
  "unmappedFinanceRowsCount": 0
}
```

Notes:

- `activeCooldowns` is the full list across categories for the seller.
- `contentApi`, `financeApi`, `commonApi`, `sellerInfoApi` are filtered summaries for specific frontend widgets.
- `lastFailedSyncError` is sanitized and truncated.
- Frontend should use this endpoint as the first request for finance dashboard boot.

## WB Product Sync Flow

### `POST /api/v1/wb/products/sync?store_id={id}&full=false&max_batches=1`

Purpose:

- Pull active WB cards from `/content/v2/get/cards/list`.
- Persist product records locally before finance analytics.

Response:

```json
{
  "status": "completed",
  "totalSynced": 120,
  "cursorUpdatedAt": "2026-05-18T08:00:00+00:00",
  "cursorNmId": 1022471872,
  "batches": 2
}
```

Flow:

- Run before finance analytics if product catalog is stale.
- Backend uses ascending cursor order and resumes from saved `updatedAt + nmID`.
- Duplicate rows are upserted by seller + `nmId`.

### `GET /api/v1/wb/products/sync/status?store_id={id}`

Response example:

```json
{
  "status": "completed",
  "cursorUpdatedAt": "2026-05-18T08:00:00+00:00",
  "cursorNmId": 1022471872,
  "totalSynced": 120,
  "lastError": null,
  "startedAt": "2026-05-18T08:10:00+00:00",
  "finishedAt": "2026-05-18T08:13:00+00:00"
}
```

Statuses seen by frontend:

- `idle`
- `running`
- `completed`
- `failed`
- `rate_limited`

Safe sync trigger guidance:

- Check `GET /api/v1/finance/system-status` first.
- If `contentApi.inCooldown=true`, do not auto-trigger product sync.
- If current status is `running`, do not send another sync request.

## WB Product List Contract

### `GET /api/v1/wb/products?store_id={id}&nmId=&vendorCode=&sku=&title=&page=1&perPage=100`

Response:

```json
{
  "items": [
    {
      "id": 1,
      "nmId": 1022471872,
      "imtId": 1991018770,
      "vendorCode": "D8013-XANH",
      "brand": "Brand",
      "title": "Shorts",
      "description": "text",
      "subjectId": 1,
      "subjectName": "Шорты",
      "photoBigUrl": "https://...",
      "photoSquareUrl": "https://...",
      "sizes": [],
      "skus": ["123"],
      "characteristics": [],
      "rawData": {}
    }
  ],
  "page": 1,
  "perPage": 100,
  "total": 1
}
```

Notes:

- `rawData` is preserved WB content payload.
- `sizes`, `skus`, and `characteristics` are always arrays.
- `imtId`, `vendorCode`, `brand`, `title`, `description`, `subjectId`, `subjectName`, image URLs can be null.

### `GET /api/v1/wb/products/{product_id}?store_id={id}`

- Returns the same product item shape.
- `404 product_not_found` if product does not belong to the current user store.

## Finance Settings Flow

### `GET /api/v1/finance/settings?store_id={id}`
### `PUT /api/v1/finance/settings?store_id={id}`

Response:

```json
{
  "id": 1,
  "sellerId": 12,
  "currency": "RUB",
  "defaultTaxMode": "percent",
  "defaultTaxRate": "0.0600",
  "taxBase": "profit",
  "defaultPackagingCost": "0.0000",
  "defaultLabelingCost": "0.0000",
  "defaultShippingToWarehouseCost": "0.0000",
  "defaultOtherUnitCost": "0.0000"
}
```

Request body example:

```json
{
  "currency": "RUB",
  "default_tax_mode": "percent",
  "default_tax_rate": "0.06",
  "tax_base": "profit",
  "default_packaging_cost": "4.5"
}
```

Notes:

- Request body uses snake_case.
- Response uses camelCase.
- Money values are strings.

## Product Finance Setting Flow

### `GET /api/v1/finance/product-settings?store_id={id}&page=1&perPage=100`

### `GET /api/v1/finance/product-settings/{product_id}?store_id={id}`

The `{product_id}` endpoint returns the same list wrapper shape because a product can have multiple effective-dated settings.

Response:

```json
{
  "items": [
    {
      "id": 10,
      "sellerId": 12,
      "productId": 1,
      "costPrice": "100.0000",
      "costCurrency": "RUB",
      "packagingCost": "5.0000",
      "labelingCost": "2.0000",
      "shippingToWarehouseCost": "3.0000",
      "otherUnitCost": "0.0000",
      "taxMode": "percent",
      "taxRate": "0.0600",
      "taxBase": "profit",
      "effectiveFrom": "2026-05-01",
      "effectiveTo": null,
      "note": null
    }
  ],
  "page": 1,
  "perPage": 100,
  "total": 1
}
```

### `PUT /api/v1/finance/product-settings/{product_id}?store_id={id}`

Request example:

```json
{
  "cost_price": "100",
  "cost_currency": "RUB",
  "packaging_cost": "5",
  "labeling_cost": "2",
  "shipping_to_warehouse_cost": "3",
  "other_unit_cost": "0",
  "tax_mode": "percent",
  "tax_rate": "0.06",
  "tax_base": "profit",
  "effective_from": "2026-05-01",
  "effective_to": null,
  "note": "summer batch"
}
```

Validation notes:

- Overlapping effective periods for the same product are rejected.
- Negative money values are rejected.
- `effective_to` must be greater than or equal to `effective_from`.

### `GET /api/v1/finance/products/missing-settings?store_id={id}`

Response:

```json
{
  "items": [
    {
      "id": 1,
      "nmId": 1022471872,
      "vendorCode": "D8013-XANH",
      "title": "Shorts"
    }
  ]
}
```

### CSV Template and Import

- `GET /api/v1/finance/product-settings/export-template?store_id={id}`
  - returns `text/csv`
- `POST /api/v1/finance/product-settings/import?store_id={id}`
  - multipart form with `file`

Import response:

```json
{
  "imported": 3,
  "errors": [
    {
      "row": 4,
      "error": "Product not found."
    }
  ]
}
```

## External Cost Flow

### `GET /api/v1/finance/external-costs?store_id={id}&page=1&perPage=100`
### `POST /api/v1/finance/external-costs?store_id={id}`
### `PUT /api/v1/finance/external-costs/{id}?store_id={id}`
### `DELETE /api/v1/finance/external-costs/{id}?store_id={id}`

Response item:

```json
{
  "id": 1,
  "sellerId": 12,
  "costDate": "2026-05-18",
  "periodFrom": "2026-05-01",
  "periodTo": "2026-05-31",
  "costType": "ads",
  "amount": "1500.0000",
  "currency": "RUB",
  "allocationMethod": "BY_REVENUE",
  "productId": null,
  "note": "campaign"
}
```

Create or update request example:

```json
{
  "cost_date": "2026-05-18",
  "period_from": "2026-05-01",
  "period_to": "2026-05-31",
  "cost_type": "ads",
  "amount": "1500",
  "currency": "RUB",
  "allocation_method": "BY_REVENUE",
  "product_id": null,
  "note": "campaign"
}
```

### `GET /api/v1/finance/external-costs/preview-allocation?store_id={id}&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`

Response:

```json
{
  "items": [
    {
      "productId": 1,
      "nmId": 1022471872,
      "vendorCode": "D8013-XANH",
      "allocatedAmount": "375.0000"
    }
  ]
}
```

## Finance Sync Flow

### `POST /api/v1/finance/reports/sync?store_id={id}`

Request:

```json
{
  "date_from": "2026-05-01",
  "date_to": "2026-05-07",
  "period": "daily",
  "force": false
}
```

Response:

```json
{
  "status": "completed",
  "rowsInserted": 700,
  "lastRrdId": 123456789
}
```

Backend behavior:

- New ranges start with `rrdId=0`.
- Resume uses last saved `rrdId`.
- Stops on `204` or empty list.
- Prevents duplicates by seller + `rrdId`.
- Preserves full raw WB row in JSONB.

### `GET /api/v1/finance/reports/sync/status?store_id={id}&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&period=daily`

Response:

```json
{
  "status": "completed",
  "lastRrdId": 123456789,
  "totalRows": 700,
  "lastError": null
}
```

Possible statuses:

- `idle`
- `running`
- `completed`
- `failed`
- `rate_limited`

Safe sync trigger guidance:

- Check `GET /api/v1/finance/system-status` first.
- If `financeApi.inCooldown=true`, do not auto-trigger finance sync.
- If sync status is already `running`, do not send a second sync request for the same selected range.

## Raw Finance Rows

### `GET /api/v1/finance/reports/raw?store_id={id}&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&limit=100`

Response:

```json
{
  "items": [
    {
      "id": 1,
      "rrdId": 123456789,
      "nmId": 1022471872,
      "vendorCode": "D8013-XANH",
      "rawData": {}
    }
  ]
}
```

Notes:

- Intended for debugging and reconciliation views, not default dashboard rendering.
- `limit` max is `1000`.

## Dashboard Cards and Summary Schema

### `GET /api/v1/finance/reports/summary?store_id={id}&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`

Response:

```json
{
  "period": {
    "dateFrom": "2026-05-01",
    "dateTo": "2026-05-07"
  },
  "grossRevenue": "10000.0000",
  "forPay": "8200.0000",
  "wbCosts": "900.0000",
  "cogs": "500.0000",
  "externalAllocatedCosts": "250.0000",
  "profitBeforeTax": "6550.0000",
  "taxAmount": "393.0000",
  "profitAfterTax": "6157.0000",
  "profitMargin": "0.6157",
  "costCompletenessPercent": "0.8000",
  "rowsCount": 42,
  "productsCount": 8
}
```

Field meanings:

- `grossRevenue`: summed retail amount before payout.
- `forPay`: payout amount from WB detailed rows.
- `wbCosts`: WB commission, logistics, storage, deductions, penalties, and related WB-side costs.
- `cogs`: product cost of goods sold from product finance settings.
- `externalAllocatedCosts`: manually tracked external costs allocated into the selected range.
- `profitBeforeTax`: `forPay - wbCosts - cogs - externalAllocatedCosts`.
- `taxAmount`: derived from product or seller tax settings.
- `profitAfterTax`: `profitBeforeTax - taxAmount`.
- `profitMargin`: `profitAfterTax / grossRevenue`.
- `costCompletenessPercent`: ratio of rows/products covered by finance settings.

## Timeline Chart Schema

### `GET /api/v1/finance/reports/timeline?store_id={id}&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&group_by=day|week|month|year`

Response:

```json
{
  "items": [
    {
      "bucket": "2026-05-01",
      "forPay": "1200.0000"
    }
  ]
}
```

Notes:

- `group_by` values: `day`, `week`, `month`, `year`
- Current timeline contract only returns `forPay` per bucket.
- Frontend should not assume additional metrics exist in each bucket.

## Product Table Schema

### `GET /api/v1/finance/reports/products?store_id={id}&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&sort=profitAfterTax&order=desc&page=1&perPage=100`

Response:

```json
{
  "items": [
    {
      "productId": 1,
      "nmId": 1022471872,
      "vendorCode": "D8013-XANH",
      "title": "Shorts",
      "quantity": "10.0000",
      "grossRevenue": "5000.0000",
      "forPay": "4100.0000",
      "wbCosts": "400.0000",
      "cogs": "1200.0000",
      "externalAllocatedCosts": "100.0000",
      "profitBeforeTax": "2400.0000",
      "taxAmount": "144.0000",
      "profitAfterTax": "2256.0000",
      "profitMargin": "0.4512",
      "hasCostSettings": true,
      "costMeta": {
        "costPrice": "100.0000",
        "packagingCost": "5.0000",
        "labelingCost": "2.0000",
        "shippingToWarehouseCost": "3.0000",
        "otherUnitCost": "0.0000"
      }
    }
  ],
  "page": 1,
  "perPage": 100,
  "total": 1
}
```

Notes:

- `sort` and `order` are string query params.
- Backend paginates after computing the full breakdown.
- `productId` can be null if a finance row cannot be mapped to a synced product.
- `hasCostSettings=false` means frontend should flag incomplete cost coverage.

Pagination parameters used in this backend:

- `page`: 1-based integer
- `perPage`: integer
- Product, product-settings, and external-cost list endpoints default to `perPage=100`
- `perPage` max is `500` on paginated list endpoints unless otherwise stated
- Raw finance rows use `limit` instead of `page/perPage`

## Cost Breakdown Schema

### `GET /api/v1/finance/reports/cost-breakdown?store_id={id}&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`

Response:

```json
{
  "wbCosts": "900.0000",
  "cogs": "500.0000",
  "externalAllocatedCosts": "250.0000"
}
```

## Insights Schema

### `GET /api/v1/finance/reports/insights?store_id={id}&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`

Response:

```json
{
  "items": [
    {
      "type": "negative_profit",
      "level": "danger",
      "message": "1 products are losing money.",
      "affectedMetric": "profitAfterTax",
      "productIds": [1],
      "recommendedAction": "Review unit cost settings, taxes, and delivery-heavy products."
    }
  ]
}
```

Notes:

- `level` values: `info`, `warning`, `danger`
- Insights are deterministic backend rules, not free-form AI output.

## Reconciliation Flow

### `GET /api/v1/finance/reports/reconciliation?store_id={id}&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&period=daily`

Response:

```json
{
  "warning": null,
  "calculatedSummary": {
    "period": {
      "dateFrom": "2026-05-01",
      "dateTo": "2026-05-07"
    },
    "grossRevenue": "10000.0000",
    "forPay": "8200.0000",
    "wbCosts": "900.0000",
    "cogs": "500.0000",
    "externalAllocatedCosts": "250.0000",
    "profitBeforeTax": "6550.0000",
    "taxAmount": "393.0000",
    "profitAfterTax": "6157.0000",
    "profitMargin": "0.6157",
    "costCompletenessPercent": "0.8000",
    "rowsCount": 42,
    "productsCount": 8
  },
  "reportListCount": 7,
  "reportListTotals": {
    "retailAmountSum": "10000.0000",
    "forPaySum": "8200.0000",
    "deliveryServiceSum": "900.0000"
  },
  "differences": {
    "retailAmountSum": "0.0000",
    "forPaySum": "0.0000",
    "deliveryServiceSum": "0.0000"
  }
}
```

Notes:

- `warning` can be non-null if list reconciliation is unavailable or partial.

## Gemini Analysis Flow

### `POST /api/v1/finance/ai/analyze?store_id={id}`

Request:

```json
{
  "date_from": "2026-05-01",
  "date_to": "2026-05-07",
  "group_by": "day"
}
```

Response:

```json
{
  "snapshotId": 1,
  "analysis": {
    "summary": "text",
    "insights": []
  }
}
```

### `GET /api/v1/finance/ai/snapshots?store_id={id}`

Response:

```json
{
  "items": [
    {
      "id": 1,
      "dateFrom": "2026-05-01",
      "dateTo": "2026-05-07",
      "aiAnalysis": {
        "summary": "text"
      }
    }
  ]
}
```

Flow notes:

- If Gemini key is not configured, backend falls back gracefully and analysis remains deterministic-safe.
- Frontend should use `system-status.geminiConfigured` to decide whether to advertise AI-enhanced analysis.

## Sync-In-Progress States

- Product sync in progress:
  - show spinner on product sync action
  - disable repeated sync submit
  - poll `/api/v1/wb/products/sync/status`
- Finance sync in progress:
  - show spinner on finance sync action
  - disable repeated sync submit for the same range
  - poll `/api/v1/finance/reports/sync/status`
- AI analysis generation in progress:
  - frontend should keep analyze action disabled until the analyze request resolves
  - there is no separate analysis job queue endpoint in the current backend

## Date, Timezone, and Money Rules

- All money values are serialized as strings.
- Frontend must not assume floats.
- Backend uses strict `date_from <= date_to` validation.
- Date query params use `YYYY-MM-DD`.
- Datetime status fields are ISO-8601 strings.
- WB source datetime fields may be absent or null; backend handles null safely.

## Known Limitations

- Optional Phase 12 acquiring-detail expansion is still not implemented as a separate feature.
- Timeline endpoint currently returns only `forPay` per bucket.
- Product settings import is CSV-only.
- Product sync and finance sync remain manual actions from frontend.
- `system-status` is local-state only; it does not prove WB is live at call time.
- Some request bodies use snake_case while response bodies use camelCase; frontend must not normalize blindly.

## Endpoints Not Yet Live Validated

- Finance detailed report endpoint has backend test coverage and production-safe sync logic, but this document does not claim a fresh live validation for every detailed-row field shape in the current token context.
- Reconciliation report-list behavior may vary by seller permissions and has not been fully live-validated for every account type.
- System status endpoint is local-state only by design and intentionally does not perform live WB verification.
