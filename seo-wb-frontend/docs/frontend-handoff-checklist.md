# Frontend Handoff Checklist

## Purpose

This checklist is for the frontend agent implementing the Wildberries Finance UI against the frozen backend contract.

## Read First

- Read `docs/frontend-contract-report.md` as the primary contract.
- Read `docs/wb-live-response-shapes.md` for real observed WB response caveats.
- Do not infer extra backend fields from backend code when the contract doc already defines the response.

## Recommended Page Order

1. Finance dashboard shell with store selector integration and system status boot flow
2. Product sync and synced product list
3. Seller finance settings
4. Product finance settings and missing-settings workflow
5. External costs and allocation preview
6. Finance sync controls and dashboard reports
7. Insights and reconciliation
8. Gemini analysis and snapshot history

## Pages To Build

### Finance Dashboard

- Uses:
  - `GET /api/v1/finance/system-status`
  - `GET /api/v1/finance/reports/summary`
  - `GET /api/v1/finance/reports/timeline`
  - `GET /api/v1/finance/reports/cost-breakdown`
  - `GET /api/v1/finance/reports/insights`
- Dashboard cards:
  - gross revenue
  - for pay
  - WB costs
  - COGS
  - external allocated costs
  - profit before tax
  - tax amount
  - profit after tax
  - profit margin
  - cost completeness percent
  - rows count
  - products count
- Required UI states:
  - initial loading
  - no data yet
  - sync running
  - cooldown active
  - partial readiness with missing settings

### Product Sync Page or Panel

- Uses:
  - `POST /api/v1/wb/products/sync`
  - `GET /api/v1/wb/products/sync/status`
  - `GET /api/v1/wb/products`
  - `GET /api/v1/wb/products/{product_id}`
- Required controls:
  - sync button
  - optional full sync toggle only if UX needs it
  - product search filters
  - pagination controls
- Table columns:
  - image
  - nmId
  - imtId
  - vendorCode
  - title
  - brand
  - subjectName
  - skus

### Seller Finance Settings Page

- Uses:
  - `GET /api/v1/finance/settings`
  - `PUT /api/v1/finance/settings`
- Required form fields:
  - currency
  - default tax mode
  - default tax rate
  - tax base
  - default packaging cost
  - default labeling cost
  - default shipping to warehouse cost
  - default other unit cost

### Product Finance Settings Page

- Uses:
  - `GET /api/v1/finance/product-settings`
  - `GET /api/v1/finance/product-settings/{product_id}`
  - `PUT /api/v1/finance/product-settings/{product_id}`
  - `GET /api/v1/finance/products/missing-settings`
  - `GET /api/v1/finance/product-settings/export-template`
  - `POST /api/v1/finance/product-settings/import`
- Required table columns:
  - product id
  - nmId if shown through joined product UI
  - vendorCode
  - title
  - costPrice
  - packagingCost
  - labelingCost
  - shippingToWarehouseCost
  - otherUnitCost
  - taxMode
  - taxRate
  - effectiveFrom
  - effectiveTo
- Required form fields:
  - all editable cost and tax fields
  - effective from
  - effective to
  - note
- Required UI states:
  - missing finance settings warning
  - overlapping date-range validation failure
  - CSV import success and row-level import errors

### External Costs Page

- Uses:
  - `GET /api/v1/finance/external-costs`
  - `POST /api/v1/finance/external-costs`
  - `PUT /api/v1/finance/external-costs/{id}`
  - `DELETE /api/v1/finance/external-costs/{id}`
  - `GET /api/v1/finance/external-costs/preview-allocation`
- Required table columns:
  - costDate
  - periodFrom
  - periodTo
  - costType
  - amount
  - currency
  - allocationMethod
  - productId
  - note

### Finance Sync and Reporting Page

- Uses:
  - `POST /api/v1/finance/reports/sync`
  - `GET /api/v1/finance/reports/sync/status`
  - `GET /api/v1/finance/reports/raw`
  - `GET /api/v1/finance/reports/products`
  - `GET /api/v1/finance/reports/reconciliation`
- Required controls:
  - date from
  - date to
  - period selector
  - sync button
  - raw rows debug drawer if implemented

### Gemini Analysis Panel

- Uses:
  - `POST /api/v1/finance/ai/analyze`
  - `GET /api/v1/finance/ai/snapshots`
- Required UI:
  - analyze button
  - current analysis display
  - snapshot history list
  - Gemini unavailable fallback state

## Chart Data Format

- Timeline endpoint returns:
  - `items[].bucket`
  - `items[].forPay`
- Frontend must parse money strings for display only.
- Frontend must not assume timeline includes profit, revenue, or cost series unless the backend contract is extended later.

## Required UI States

- loading
- empty
- validation error
- backend error
- cooldown active
- sync running
- sync completed
- stale store selection changed
- Gemini not configured
- missing finance settings present
- unmapped finance rows present

## Cooldown Handling

- Always check `GET /api/v1/finance/system-status` before showing sync actions as ready.
- If any relevant API block has `inCooldown=true`, disable the related sync action.
- Show `retryAfterSeconds` as a human countdown.
- Do not implement automatic retry loops against sync endpoints.
- Refresh system status manually or on a conservative timer.

## Missing Finance Settings Handling

- Read:
  - `hasProductsMissingFinanceSettings`
  - `missingFinanceSettingsCount`
  - `GET /api/v1/finance/products/missing-settings`
- Show a warning banner on dashboard and product settings pages.
- Link directly to the product settings page or import flow.

## Unmapped Finance Rows Handling

- Read:
  - `hasUnmappedFinanceRows`
  - `unmappedFinanceRowsCount`
- Show a warning banner in dashboard and reporting views.
- Explain that some finance rows could not be linked to a synced WB product.
- Do not fabricate product names for unmapped rows.

## Safe Sync Trigger Rules

- Product sync:
  - check `contentApi.inCooldown`
  - check current product sync status is not `running`
- Finance sync:
  - check `financeApi.inCooldown`
  - check current finance sync status is not `running`
- If status is `rate_limited`, use backend error and system status to decide when retry is allowed.

## What Must Not Be Done By Frontend

- Do not send WB token, seller id, or Gemini API key to these endpoints.
- Do not compute finance profits using floats.
- Do not guess undocumented fields.
- Do not auto-retry WB-sensitive sync endpoints aggressively.
- Do not assume `system-status` performs a live WB health call.
- Do not assume request and response casing are identical.
- Do not bypass store ownership flow.
