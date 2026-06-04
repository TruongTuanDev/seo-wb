# Wildberries Finance Integration Design

## Scope

This backend already has working modules for authentication, user ownership, store management, Wildberries content operations, encrypted token storage, Gemini integration, PostgreSQL, Alembic migrations, and pytest coverage. The finance service will extend those pieces instead of replacing them.

## Existing Modules Reused

- `app.api.deps.get_current_user`
  Reuse current JWT/cookie auth and CSRF rules for all finance endpoints.
- `app.api.deps.get_owned_store`
  Reuse store ownership enforcement. Finance operations stay scoped to the authenticated user's store.
- `app.models.store.Store`
  Reuse the current store record as the source of the encrypted Wildberries token already stored per shop.
- `app.core.security.encrypt_secret` and `decrypt_secret`
  Reuse current encryption flow for token access. No new secret storage system will be introduced.
- `app.services.wb_client.WildberriesClient`
  Reuse transport, retry, and error-handling patterns as the base reference for a new category-aware WB client layer.
- `app.services.gemini_analyzer.GeminiAnalyzer`
  Reuse the existing Gemini SDK dependency and configuration conventions. Finance AI analysis will use the same `GEMINI_API_KEY` and `GEMINI_MODEL` settings with a separate service.
- `app.db.session.Base`, `engine`, `SessionLocal`
  Reuse SQLAlchemy setup, PostgreSQL conventions, and Alembic migration flow already in place.
- `tests/*`
  Reuse current pytest style with dependency overrides, local SQLite test DB fixtures, and mocked remote integrations.

## New Modules Needed

- `app.models.seller`
  Seller identity metadata returned by WB seller/common APIs.
- `app.models.wb_product`
  Synced WB product catalog rows and incremental sync state.
- `app.models.finance`
  Seller finance settings, product finance settings, external costs, finance report rows, sync state, AI snapshots, diagnostic logs.
- `app.schemas.finance`
  Request/response schemas for diagnostics, sync, settings, dashboard, insights, and AI analysis.
- `app.services.wb_base_client`
  Common category-aware WB HTTP base client with rate limiting and sanitized diagnostics.
- `app.services.wb_finance_client`
  Finance API client for sales report sync and optional reconciliation/report-list calls.
- `app.services.wb_common_client`
  Common API client for seller diagnostics if the response surface differs from content/finance clients.
- `app.services.wb_product_sync_service`
  Product sync orchestration and cursor persistence.
- `app.services.finance_settings_service`
  Seller/product finance settings and external cost CRUD rules.
- `app.services.finance_sync_service`
  Finance detailed report sync with resume support and row normalization.
- `app.services.finance_aggregation_service`
  Summary, timeline, product, cost breakdown, and deterministic insight calculations.
- `app.services.profit_calculation_service`
  Exact `Decimal`-based tax and profit calculation logic.
- `app.services.finance_ai_analysis_service`
  Sanitized Gemini-based finance analysis and snapshot persistence.
- `app.api.routes.finance`
  Finance endpoints under the existing FastAPI app.

## Tables Added Or Extended

- New `sellers`
  Stores WB seller identity and becomes the parent record for synced products and finance artifacts.
- New `wb_products`
  Stores synced WB product cards, arrays/JSONB fields, and raw payload.
- New `wb_product_sync_state`
  Stores incremental cursor and sync status.
- New `seller_finance_settings`
  Store-level default tax and unit costs.
- New `product_finance_settings`
  Product cost history with effective date ranges.
- New `external_costs`
  Shop-level or product-directed external cost records.
- New `wb_finance_report_rows`
  Raw and normalized detailed finance rows with JSONB preservation.
- New `wb_finance_sync_state`
  Resume state for finance sync by date window.
- New `finance_analysis_snapshots`
  Cached deterministic and AI-facing report snapshots.
- New `api_diagnostic_logs`
  Sanitized live-test and API-diagnostic records.
- Existing `stores`
  Remains the token ownership root. No duplicate seller/shop/token system will be introduced.

## Finance Row to Product Mapping

- Primary link: `(seller_id, nm_id)` from finance row to `wb_products`.
- Fallback 1: `(seller_id, sku)` against `wb_products.skus`.
- Fallback 2: `(seller_id, vendor_code)` against `wb_products.vendor_code`.
- Persist `product_id` on finance rows once matched.
- Profit analytics depend on product sync first. If a row cannot be mapped, aggregations must flag cost incompleteness instead of guessing.

## WB Token Loading

- Finance endpoints will accept the existing `store_id`.
- The store will be loaded with `get_owned_store`.
- The WB token will be decrypted from `Store.wb_api_key_encrypted` using `decrypt_secret`.
- The new WB clients will receive the decrypted token in-memory only.
- Tokens must never be printed, returned, or stored in diagnostic logs.

## Gemini Reuse Strategy

- Reuse current Gemini package import path and global settings.
- Finance AI analysis will build a sanitized aggregate payload only.
- Raw finance rows, WB tokens, KIZ values, and secrets will not be sent unless explicitly enabled in a future upgrade.
- Missing Gemini key must not break the finance dashboard or non-AI endpoints.

## Live Test Strategy

- Follow the plan's safe-live-test rules and existing repo conventions.
- Live WB tests stay read-only and minimal by default.
- Stop on the first clear rate-limit signal for the relevant host/method class.
- Append every live attempt to `docs/wb-live-test-report.md`.
- Gate live execution on `WB_LIVE_TESTS=1` and a valid encrypted store token or explicit finance/common token config if later introduced.
- Product sync must run before finance profit analytics live validation.

## Phase Ordering

1. Audit and documentation baseline.
2. WB client/rate-limiter foundation and diagnostics logging.
3. Seller diagnostics and product sync.
4. Finance settings and external costs.
5. Finance row sync.
6. Aggregations and deterministic insights.
7. Gemini analysis.
8. Reconciliation, bulk import/export, and performance hardening.
