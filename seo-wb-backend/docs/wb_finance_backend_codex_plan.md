# WB Finance Backend Plan for Codex

> Project: FastAPI + PostgreSQL backend for Wildberries financial reporting, product sync, cost settings, tax settings, external costs, and Gemini-based analysis.
>
> Goal: Build backend first. Frontend will be implemented later based on backend API contract and generated implementation reports.

---

## 0. Official WB API Research Summary

### 0.1 General WB API rules

Source: https://dev.wildberries.ru/en/docs/openapi/api-information

Important rules:

- Authorization is passed through the `Authorization` request header.
- Token lifetime is 180 days after creation.
- API category permissions are controlled by token category bitmask.
- Finance methods require the Finance category.
- Product cards require the Content category according to the docs section, although the current docs line for Product Cards List says Promotion category; implement token diagnostics and report actual live behavior.
- Common WB status codes:
  - `200`: success
  - `204`: no data / deleted / updated / confirmed depending on method
  - `400`: bad request
  - `401`: unauthorized or token category mismatch
  - `402`: payment required
  - `403`: access denied
  - `404`: not found
  - `409`: status update error / data conflict
  - `413`: request body too large
  - `422`: parameter processing error
  - `429`: too many requests
  - `5xx`: WB internal error
- WB uses token bucket rate limits.
- Read and respect these response headers where present:
  - `X-Ratelimit-Remaining`
  - `X-Ratelimit-Retry`
  - `X-Ratelimit-Limit`
  - `X-Ratelimit-Reset`
- Never spam retries on `429`. Sleep or reschedule based on `X-Ratelimit-Retry` or `X-Ratelimit-Reset`.
- Use `/ping` per host to verify token and host category, but do not call it aggressively. `/ping` is limited to max 3 requests per 30 seconds per host.

Recommended environment variables:

```env
WB_FINANCE_API_TOKEN=
WB_CONTENT_API_TOKEN=
WB_COMMON_API_TOKEN=
WB_FINANCE_API_BASE_URL=https://finance-api.wildberries.ru
WB_CONTENT_API_BASE_URL=https://content-api.wildberries.ru
WB_COMMON_API_BASE_URL=https://common-api.wildberries.ru
GEMINI_API_KEY=
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/db
REDIS_URL=redis://localhost:6379/0
```

---

## 1. WB Finance APIs to Implement

Source: https://dev.wildberries.ru/en/docs/openapi/financial-reports-and-accounting

### 1.1 Seller Balance

Endpoint:

```http
GET https://finance-api.wildberries.ru/api/v1/account/balance
Authorization: <Finance token>
```

Rate limit:

```text
1 request / 1 minute / seller account
interval: 1 minute
burst: 1
```

Response sample fields:

```json
{
  "currency": "RUB",
  "current": 10196.21,
  "for_withdraw": 6395.8
}
```

Use case:

- Optional dashboard card.
- Live token check after Finance module setup.

---

### 1.2 Sales Report List

Endpoint:

```http
POST https://finance-api.wildberries.ru/api/finance/v1/sales-reports/list
Authorization: <Finance token>
Content-Type: application/json
```

Purpose:

- Returns sales report list in the seller portal report table format.
- Use for report period metadata and reconciliation totals.
- Do not use this as the only data source for product-level profit calculations.

Availability:

```text
Data since: 2025-01-01
Token types: Personal, Service
Docs note: currently unavailable for some registration countries.
```

Rate limit:

```text
1 request / 1 minute / seller account
interval: 1 minute
burst: 1
```

Request schema:

```json
{
  "dateFrom": "2026-03-17",
  "dateTo": "2026-03-20",
  "limit": 1000,
  "offset": 0,
  "period": "daily"
}
```

Field rules:

- `dateFrom`: required string, RFC3339, Moscow timezone UTC+3.
- `dateTo`: required string, RFC3339, Moscow timezone UTC+3.
- `limit`: integer <= 1000, default 1000.
- `offset`: integer, default 0.
- `period`: `daily` or `weekly`, default `weekly`.

Response sample fields:

```json
[
  {
    "reportId": 307401554,
    "sellerFinanceName": "ИП Кружинин В. Р.",
    "dateFrom": "2026-03-16",
    "dateTo": "2026-03-22",
    "createDate": "2026-03-23",
    "currency": "RUB",
    "reportType": 1,
    "retailAmountSum": "258",
    "forPaySum": "183.79",
    "avgSalePercent": 0,
    "deliveryServiceSum": "2558.47",
    "paidStorageSum": "626.84",
    "paidAcceptanceSum": "243.81",
    "deductionSum": "150",
    "penaltySum": "1457.61",
    "additionalPaymentSum": "9509.71",
    "cashbackAmountSum": "2",
    "cashbackDiscountSum": "19",
    "cashbackCommissionChangeSum": "0.2",
    "paymentSchedule": "-1",
    "bankPaymentSum": "5172.94"
  }
]
```

Implementation notes:

- Store raw JSON.
- Parse numeric strings into `Decimal`.
- Use list reports for reconciliation only.
- If unavailable for the seller country, record diagnostic and continue with detail-by-period API.

---

### 1.3 Sales Report Details by Period — Primary API

Endpoint:

```http
POST https://finance-api.wildberries.ru/api/finance/v1/sales-reports/detailed
Authorization: <Finance token>
Content-Type: application/json
```

Purpose:

- Primary source for financial report rows.
- Use for date range selected by user.
- Use for product-level, order-level, daily, monthly, yearly aggregation.

Availability:

```text
Data since: 2024-01-29
```

Rate limit:

```text
1 request / 1 minute / seller account
interval: 1 minute
burst: 1
```

Request schema:

```json
{
  "dateFrom": "2026-03-17",
  "dateTo": "2026-03-20",
  "limit": 100000,
  "rrdId": 0,
  "period": "daily",
  "fields": [
    "reportId",
    "dateFrom",
    "dateTo",
    "createDate",
    "currency",
    "reportType",
    "rrdId",
    "subjectName",
    "nmId",
    "brandName",
    "vendorCode",
    "title",
    "techSize",
    "sku",
    "docTypeName",
    "quantity",
    "retailPrice",
    "retailAmount",
    "salePercent",
    "commissionPercent",
    "officeName",
    "sellerOperName",
    "orderDt",
    "saleDt",
    "rrDate",
    "retailPriceWithDisc",
    "deliveryAmount",
    "returnAmount",
    "deliveryService",
    "ppvzSalesCommission",
    "forPay",
    "acquiringFee",
    "acquiringPercent",
    "paymentProcessing",
    "acquiringBank",
    "penalty",
    "additionalPayment",
    "paidStorage",
    "deduction",
    "paidAcceptance",
    "orderId",
    "kiz",
    "cashbackAmount",
    "cashbackDiscount",
    "cashbackCommissionChange",
    "paymentSchedule",
    "deliveryMethod",
    "sellerPromoId",
    "sellerPromoDiscount",
    "agencyVat",
    "orderUid",
    "srid"
  ]
}
```

Field rules:

- `dateFrom`: required string, RFC3339, Moscow timezone UTC+3.
- `dateTo`: required string, RFC3339, Moscow timezone UTC+3.
- `limit`: integer <= 100000, default 100000.
- `rrdId`: integer, default 0.
- `period`: `daily` or `weekly`, default `weekly`.
- `fields`: optional array of strings. If omitted, all fields are returned.

Pagination:

```text
Start with rrdId = 0.
After each 200 response, get rrdId from the last row.
Next request uses that rrdId.
Repeat until response status is 204.
```

Response statuses:

- `200`: rows returned.
- `204`: no data / no more data.
- `400`, `401`, `429`: handle and persist diagnostics.

Important response fields to model:

```json
{
  "reportId": 1234567,
  "dateFrom": "2026-03-16",
  "dateTo": "2026-03-22",
  "createDate": "2026-03-23",
  "currency": "RUB",
  "reportType": 1,
  "rrdId": 1232610467,
  "giId": 123456,
  "dlvPrc": 1.8,
  "fixTariffDateFrom": "2026-03-18",
  "fixTariffDateTo": "2026-03-19",
  "subjectName": "Mini ovens",
  "nmId": 1234567,
  "brandName": "BlahBlah",
  "vendorCode": "MAB123",
  "title": "ДС тарелка",
  "techSize": "0",
  "sku": "1231312352310",
  "docTypeName": "Продажа",
  "quantity": 1,
  "retailPrice": "1249",
  "retailAmount": "367",
  "salePercent": 0,
  "commissionPercent": 24,
  "officeName": "Коледино",
  "sellerOperName": "Продажа",
  "orderDt": "2026-03-14T00:00:00Z",
  "saleDt": "2026-03-21T00:00:00Z",
  "rrDate": "2025-10-20",
  "shkId": 1239159661,
  "retailPriceWithDisc": "399.68",
  "deliveryAmount": 0,
  "returnAmount": 0,
  "deliveryService": "0",
  "productDiscountForReport": 0,
  "sellerPromo": "0",
  "spp": 25.31,
  "kvwBase": 24.15,
  "kvw": 1.81,
  "ppvzSalesCommission": "23.74",
  "forPay": "376.99",
  "ppvzReward": "0",
  "acquiringFee": "14.89",
  "acquiringPercent": 4.06,
  "paymentProcessing": "Комиссия за организацию платежа с НДС",
  "acquiringBank": "Тинькофф",
  "penalty": "231.35",
  "additionalPayment": "0",
  "rebillLogisticCost": "1.349",
  "paidStorage": "12647.29",
  "deduction": "6354",
  "paidAcceptance": "865",
  "orderId": 2816993144,
  "kiz": "...",
  "isB2b": false,
  "trbxId": "WB-TRBX-1234567",
  "cashbackAmount": "2",
  "cashbackDiscount": "19",
  "cashbackCommissionChange": "0.2",
  "paymentSchedule": "-1",
  "deliveryMethod": "FBS, (МГТ)",
  "sellerPromoId": 14350,
  "sellerPromoDiscount": 3,
  "agencyVat": 0,
  "orderUid": "id375f16c4bec295d9995393af803ff7b",
  "srid": "0f1c3999172603062979867564654dac5b702849"
}
```

Implementation notes:

- Do not call this synchronously in a frontend request for large ranges.
- Use background jobs and sync state.
- Save raw data and normalized columns.
- Use `Decimal` for all money values.
- Deduplicate by `(seller_id, rrd_id)`.
- Add a live test with a small date range first.
- Use docs field names exactly: new finance API uses camelCase. Deprecated Statistics API uses snake_case; do not mix them in the primary model.

---

### 1.4 Deprecated Realization Sales Report — Do Not Use for New Feature

Endpoint:

```http
GET https://statistics-api.wildberries.ru/api/v5/supplier/reportDetailByPeriod
```

Docs status:

```text
Deprecated. Do not build new finance service on this endpoint.
```

Notes:

- Keep optional compatibility only if the current project already has legacy support.
- Main implementation must use `POST /api/finance/v1/sales-reports/detailed`.

---

### 1.5 Acquiring Expenses APIs — Upgrade Phase

Endpoints:

```http
POST https://finance-api.wildberries.ru/api/finance/v1/acquiring/list
POST https://finance-api.wildberries.ru/api/finance/v1/acquiring/detailed
POST https://finance-api.wildberries.ru/api/finance/v1/acquiring/detailed/{reportId}
```

Use case:

- Upgrade module for separate acquiring reconciliation.
- Only available for sellers from Russia according to WB docs.

Rate limit:

```text
1 request / 1 minute / seller account
interval: 1 minute
burst: 1
```

MVP status:

- Do not block MVP on acquiring detail API because `sales-reports/detailed` already contains `acquiringFee`, `acquiringPercent`, `paymentProcessing`, `acquiringBank`.
- Add as Phase 8 upgrade.

---

## 2. WB Product APIs to Implement Before Finance Analytics

Source: https://dev.wildberries.ru/en/docs/openapi/work-with-products

### 2.1 Product Cards List

Endpoint:

```http
POST https://content-api.wildberries.ru/content/v2/get/cards/list?locale=ru
Authorization: <Content token>
Content-Type: application/json
```

Purpose:

- Sync products before financial analytics.
- Finance rows contain `nmId`, `vendorCode`, `sku`, and `title`, but product sync gives product metadata, photos, dimensions, size SKUs, subject, brand, and KIZ flags.

Rate limit:

```text
Content category general limit:
1 minute: 100 requests
interval: 600 ms
burst: 5
```

Pagination request for full export:

```json
{
  "settings": {
    "sort": {
      "ascending": true
    },
    "cursor": {
      "limit": 100
    },
    "filter": {
      "withPhoto": -1
    }
  }
}
```

Incremental sync:

```text
Use ascending sort.
Save cursor.updatedAt and cursor.nmID from the last response of the previous export.
Pass saved cursor.updatedAt and cursor.nmID in the next first request.
Continue until response cursor total is less than limit.
```

Cursor sample:

```json
{
  "updatedAt": "2023-12-06T11:17:00.96577Z",
  "nmID": 370870300,
  "limit": 100
}
```

Request sample with filters:

```json
{
  "settings": {
    "sort": {
      "ascending": false
    },
    "filter": {
      "textSearch": "4603743187500888",
      "allowedCategoriesOnly": true,
      "tagIDs": [345, 415],
      "objectIDs": [235, 67],
      "brands": ["уллу", "EkkE"],
      "imtID": 328632,
      "withPhoto": -1
    },
    "cursor": {
      "updatedAt": "2023-12-06T11:17:00.96577Z",
      "nmID": 370870300,
      "limit": 100
    }
  }
}
```

Response sample fields:

```json
{
  "cards": [
    {
      "nmID": 12345678,
      "imtID": 123654789,
      "nmUUID": "01bda0b1-5c0b-736c-b2be-d0a6543e9be",
      "subjectID": 7771,
      "subjectName": "AKF системы",
      "vendorCode": "wb7f6mumjr1",
      "kizMarked": true,
      "brand": "Тест",
      "title": "Тест-система",
      "description": "Тестовое описание",
      "needKiz": false,
      "photos": [
        {
          "big": "https://.../big/1.webp",
          "c246x328": "https://.../c246x328/1.webp",
          "c516x688": "https://.../c516x688/1.webp",
          "square": "https://.../square/1.webp",
          "tm": "https://.../tm/1.webp"
        }
      ],
      "video": "https://.../index.m3u8",
      "wholesale": {
        "enabled": true,
        "quantum": 112
      },
      "dimensions": {
        "length": 55,
        "width": 40,
        "height": 15,
        "weightBrutto": 6.24,
        "isValid": false
      },
      "characteristics": [
        {
          "id": 14177449,
          "name": "Цвет",
          "value": ["красно-сиреневый"]
        }
      ],
      "sizes": [
        {
          "chrtID": 316399238,
          "techSize": "0",
          "skus": ["987456321654"]
        }
      ]
    }
  ],
  "cursor": {
    "updatedAt": "2023-12-06T11:17:00.96577Z",
    "nmID": 370870300,
    "limit": 100
  }
}
```

Implementation notes:

- Store `raw_data` JSONB.
- Product unique key: `(seller_id, nm_id)`.
- Size/SKU can be one-to-many: create `wb_product_sizes` and `wb_product_skus` or store size array JSONB for MVP.
- Photo: store primary big/square URL for frontend.
- Keep `needKiz`, `kizMarked`, `dimensions`, `characteristics` for future analytics and packaging/KIZ workflows.
- Product card list does not return trashed product cards. Implement trash sync only in upgrade phase if needed.

---

## 3. Backend Architecture

Current stack expected:

```text
FastAPI
PostgreSQL
SQLAlchemy 2.x async or SQLModel async
Alembic
Pydantic v2
httpx AsyncClient
Redis optional but recommended
Celery / RQ / Dramatiq optional but recommended for sync jobs
Gemini SDK/client already present in project
```

Target module structure:

```text
backend/
├── app/
│   ├── api/
│   │   ├── wb_health_router.py
│   │   ├── wb_product_router.py
│   │   ├── finance_settings_router.py
│   │   ├── finance_report_router.py
│   │   ├── external_cost_router.py
│   │   └── finance_ai_router.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   ├── security.py
│   │   └── rate_limiter.py
│   │
│   ├── clients/
│   │   ├── wb_base_client.py
│   │   ├── wb_finance_client.py
│   │   ├── wb_content_client.py
│   │   └── gemini_client.py
│   │
│   ├── models/
│   │   ├── seller.py
│   │   ├── wb_product.py
│   │   ├── wb_product_sync_state.py
│   │   ├── seller_finance_settings.py
│   │   ├── product_finance_settings.py
│   │   ├── external_cost.py
│   │   ├── wb_finance_report.py
│   │   ├── wb_finance_report_row.py
│   │   ├── wb_finance_sync_state.py
│   │   ├── finance_analysis_snapshot.py
│   │   └── api_diagnostic_log.py
│   │
│   ├── repositories/
│   │   ├── product_repository.py
│   │   ├── finance_report_repository.py
│   │   ├── finance_settings_repository.py
│   │   ├── external_cost_repository.py
│   │   └── diagnostic_repository.py
│   │
│   ├── schemas/
│   │   ├── wb_product_schema.py
│   │   ├── finance_settings_schema.py
│   │   ├── finance_report_schema.py
│   │   ├── external_cost_schema.py
│   │   └── finance_ai_schema.py
│   │
│   ├── services/
│   │   ├── product_sync_service.py
│   │   ├── finance_sync_service.py
│   │   ├── finance_aggregation_service.py
│   │   ├── profit_calculation_service.py
│   │   ├── cost_allocation_service.py
│   │   ├── finance_ai_analysis_service.py
│   │   └── sync_report_service.py
│   │
│   ├── workers/
│   │   ├── product_sync_tasks.py
│   │   └── finance_sync_tasks.py
│   │
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── live/wb/
│
├── alembic/
├── docs/
│   ├── wb-finance-backend-plan.md
│   ├── wb-api-field-map.md
│   ├── wb-live-test-report.md
│   ├── backend-progress-log.md
│   └── frontend-contract-report.md
└── TASKS.md
```

---

## 4. Database Schema Plan

### 4.1 `sellers`

```sql
CREATE TABLE sellers (
    id BIGSERIAL PRIMARY KEY,
    external_sid UUID,
    name TEXT,
    trade_mark TEXT,
    tin TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

MVP can use a single default seller if the project is not multi-tenant yet.

---

### 4.2 `wb_products`

```sql
CREATE TABLE wb_products (
    id BIGSERIAL PRIMARY KEY,
    seller_id BIGINT NOT NULL REFERENCES sellers(id),

    nm_id BIGINT NOT NULL,
    imt_id BIGINT,
    nm_uuid UUID,
    subject_id BIGINT,
    subject_name TEXT,
    vendor_code TEXT,
    brand TEXT,
    title TEXT,
    description TEXT,

    need_kiz BOOLEAN,
    kiz_marked BOOLEAN,

    photo_big_url TEXT,
    photo_square_url TEXT,

    length NUMERIC(12, 3),
    width NUMERIC(12, 3),
    height NUMERIC(12, 3),
    weight_brutto NUMERIC(12, 3),
    dimensions_valid BOOLEAN,

    characteristics JSONB NOT NULL DEFAULT '[]'::jsonb,
    sizes JSONB NOT NULL DEFAULT '[]'::jsonb,
    skus TEXT[] NOT NULL DEFAULT '{}',
    raw_data JSONB NOT NULL,

    wb_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (seller_id, nm_id)
);

CREATE INDEX idx_wb_products_seller_nm ON wb_products(seller_id, nm_id);
CREATE INDEX idx_wb_products_vendor_code ON wb_products(seller_id, vendor_code);
CREATE INDEX idx_wb_products_skus_gin ON wb_products USING GIN(skus);
```

---

### 4.3 `wb_product_sync_state`

```sql
CREATE TABLE wb_product_sync_state (
    id BIGSERIAL PRIMARY KEY,
    seller_id BIGINT NOT NULL REFERENCES sellers(id),
    sync_type VARCHAR(30) NOT NULL DEFAULT 'active_cards',
    cursor_updated_at TIMESTAMPTZ,
    cursor_nm_id BIGINT,
    status VARCHAR(30) NOT NULL DEFAULT 'idle',
    last_error TEXT,
    total_synced BIGINT DEFAULT 0,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (seller_id, sync_type)
);
```

---

### 4.4 `seller_finance_settings`

```sql
CREATE TABLE seller_finance_settings (
    id BIGSERIAL PRIMARY KEY,
    seller_id BIGINT NOT NULL REFERENCES sellers(id) UNIQUE,

    currency VARCHAR(10) NOT NULL DEFAULT 'RUB',

    default_tax_mode VARCHAR(50) NOT NULL DEFAULT 'NONE',
    default_tax_rate NUMERIC(8, 4) NOT NULL DEFAULT 0,
    tax_base VARCHAR(50) NOT NULL DEFAULT 'PROFIT',

    default_packaging_cost NUMERIC(18, 4) NOT NULL DEFAULT 0,
    default_labeling_cost NUMERIC(18, 4) NOT NULL DEFAULT 0,
    default_shipping_to_warehouse_cost NUMERIC(18, 4) NOT NULL DEFAULT 0,
    default_other_unit_cost NUMERIC(18, 4) NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

Recommended enum values:

```text
default_tax_mode: NONE, CUSTOM, USN_INCOME, USN_PROFIT, OSNO, PATENT, OTHER
tax_base: REVENUE, PROFIT, MANUAL
```

---

### 4.5 `product_finance_settings`

Use validity periods because cost price changes over time.

```sql
CREATE TABLE product_finance_settings (
    id BIGSERIAL PRIMARY KEY,
    seller_id BIGINT NOT NULL REFERENCES sellers(id),
    product_id BIGINT NOT NULL REFERENCES wb_products(id),

    cost_price NUMERIC(18, 4) NOT NULL DEFAULT 0,
    cost_currency VARCHAR(10) NOT NULL DEFAULT 'RUB',

    packaging_cost NUMERIC(18, 4) NOT NULL DEFAULT 0,
    labeling_cost NUMERIC(18, 4) NOT NULL DEFAULT 0,
    shipping_to_warehouse_cost NUMERIC(18, 4) NOT NULL DEFAULT 0,
    other_unit_cost NUMERIC(18, 4) NOT NULL DEFAULT 0,

    tax_mode VARCHAR(50),
    tax_rate NUMERIC(8, 4),
    tax_base VARCHAR(50),

    effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to DATE,
    note TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_product_finance_settings_lookup
ON product_finance_settings(seller_id, product_id, effective_from, effective_to);
```

Do not use only `UNIQUE(product_id)` because historical costs are necessary for old reports.

---

### 4.6 `external_costs`

```sql
CREATE TABLE external_costs (
    id BIGSERIAL PRIMARY KEY,
    seller_id BIGINT NOT NULL REFERENCES sellers(id),

    cost_date DATE NOT NULL,
    period_from DATE,
    period_to DATE,
    cost_type VARCHAR(100) NOT NULL,
    amount NUMERIC(18, 4) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'RUB',

    allocation_method VARCHAR(50) NOT NULL DEFAULT 'BY_REVENUE',
    product_id BIGINT REFERENCES wb_products(id),
    note TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

Recommended allocation methods:

```text
BY_REVENUE
BY_SOLD_QUANTITY
EQUAL_BY_PRODUCT
DIRECT_PRODUCT
MANUAL_NONE
```

---

### 4.7 `wb_finance_report_rows`

```sql
CREATE TABLE wb_finance_report_rows (
    id BIGSERIAL PRIMARY KEY,
    seller_id BIGINT NOT NULL REFERENCES sellers(id),

    report_id BIGINT,
    date_from DATE,
    date_to DATE,
    create_date DATE,
    currency VARCHAR(10),
    report_type INTEGER,
    rrd_id BIGINT NOT NULL,

    nm_id BIGINT,
    brand_name TEXT,
    vendor_code TEXT,
    title TEXT,
    subject_name TEXT,
    tech_size TEXT,
    sku TEXT,

    doc_type_name TEXT,
    seller_oper_name TEXT,
    quantity INTEGER DEFAULT 0,

    retail_price NUMERIC(18, 4) DEFAULT 0,
    retail_amount NUMERIC(18, 4) DEFAULT 0,
    retail_price_with_disc NUMERIC(18, 4) DEFAULT 0,
    sale_percent NUMERIC(8, 4) DEFAULT 0,
    commission_percent NUMERIC(8, 4) DEFAULT 0,

    office_name TEXT,
    order_dt TIMESTAMPTZ,
    sale_dt TIMESTAMPTZ,
    rr_date DATE,
    shk_id BIGINT,

    delivery_amount INTEGER DEFAULT 0,
    return_amount INTEGER DEFAULT 0,
    delivery_service NUMERIC(18, 4) DEFAULT 0,

    ppvz_sales_commission NUMERIC(18, 4) DEFAULT 0,
    for_pay NUMERIC(18, 4) DEFAULT 0,
    acquiring_fee NUMERIC(18, 4) DEFAULT 0,
    acquiring_percent NUMERIC(8, 4) DEFAULT 0,
    payment_processing TEXT,
    acquiring_bank TEXT,

    penalty NUMERIC(18, 4) DEFAULT 0,
    additional_payment NUMERIC(18, 4) DEFAULT 0,
    rebill_logistic_cost NUMERIC(18, 4) DEFAULT 0,
    paid_storage NUMERIC(18, 4) DEFAULT 0,
    deduction NUMERIC(18, 4) DEFAULT 0,
    paid_acceptance NUMERIC(18, 4) DEFAULT 0,

    order_id BIGINT,
    order_uid TEXT,
    srid TEXT,
    kiz TEXT,
    is_b2b BOOLEAN,
    delivery_method TEXT,

    cashback_amount NUMERIC(18, 4) DEFAULT 0,
    cashback_discount NUMERIC(18, 4) DEFAULT 0,
    cashback_commission_change NUMERIC(18, 4) DEFAULT 0,
    agency_vat NUMERIC(18, 4) DEFAULT 0,

    product_id BIGINT REFERENCES wb_products(id),
    raw_data JSONB NOT NULL,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (seller_id, rrd_id)
);

CREATE INDEX idx_finance_rows_seller_sale_dt ON wb_finance_report_rows(seller_id, sale_dt);
CREATE INDEX idx_finance_rows_seller_rr_date ON wb_finance_report_rows(seller_id, rr_date);
CREATE INDEX idx_finance_rows_nm ON wb_finance_report_rows(seller_id, nm_id);
CREATE INDEX idx_finance_rows_vendor_code ON wb_finance_report_rows(seller_id, vendor_code);
CREATE INDEX idx_finance_rows_sku ON wb_finance_report_rows(seller_id, sku);
CREATE INDEX idx_finance_rows_doc_type ON wb_finance_report_rows(seller_id, doc_type_name);
```

---

### 4.8 `wb_finance_sync_state`

```sql
CREATE TABLE wb_finance_sync_state (
    id BIGSERIAL PRIMARY KEY,
    seller_id BIGINT NOT NULL REFERENCES sellers(id),

    date_from DATE NOT NULL,
    date_to DATE NOT NULL,
    period VARCHAR(20) NOT NULL DEFAULT 'daily',

    last_rrd_id BIGINT NOT NULL DEFAULT 0,
    status VARCHAR(30) NOT NULL DEFAULT 'idle',
    total_rows BIGINT DEFAULT 0,
    last_error TEXT,

    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (seller_id, date_from, date_to, period)
);
```

---

### 4.9 `finance_analysis_snapshots`

```sql
CREATE TABLE finance_analysis_snapshots (
    id BIGSERIAL PRIMARY KEY,
    seller_id BIGINT NOT NULL REFERENCES sellers(id),

    date_from DATE NOT NULL,
    date_to DATE NOT NULL,
    group_by VARCHAR(20) NOT NULL,

    summary JSONB NOT NULL,
    product_breakdown JSONB,
    cost_breakdown JSONB,
    insights JSONB,
    ai_analysis JSONB,

    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

### 4.10 `api_diagnostic_logs`

```sql
CREATE TABLE api_diagnostic_logs (
    id BIGSERIAL PRIMARY KEY,
    seller_id BIGINT REFERENCES sellers(id),
    provider VARCHAR(50) NOT NULL DEFAULT 'wildberries',
    category VARCHAR(50) NOT NULL,
    endpoint TEXT NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER,
    request_meta JSONB,
    response_meta JSONB,
    error_text TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Use this for live test reports and debugging without exposing tokens.

---

## 5. Profit Calculation Rules

### 5.1 Core sums from WB finance rows

Use `Decimal` everywhere.

```text
gross_revenue = SUM(retailAmount)
for_pay = SUM(forPay)
commission = SUM(ppvzSalesCommission)
logistics = SUM(deliveryService)
acquiring = SUM(acquiringFee)
storage = SUM(paidStorage)
acceptance = SUM(paidAcceptance)
penalty = SUM(penalty)
deduction = SUM(deduction)
additional_payment = SUM(additionalPayment)
returns_count = SUM(returnAmount)
delivery_count = SUM(deliveryAmount)
sold_quantity = SUM(quantity where docTypeName indicates sale)
```

### 5.2 WB costs

```text
wb_costs =
    commission
  + logistics
  + acquiring
  + storage
  + acceptance
  + penalty
  + deduction
  - additional_payment
```

Do not double-count if `forPay` is already net of some WB deductions. Keep both:

```text
wb_reported_for_pay = SUM(forPay)
wb_costs_breakdown = separated cost view
```

For profit, define calculation mode explicitly:

```text
Mode A, recommended for MVP:
profit_before_tax = for_pay - cogs - external_allocated_costs

Mode B, analytical breakdown:
profit_before_tax_estimated = gross_revenue - wb_costs - cogs - external_allocated_costs
```

Return both if possible and label clearly.

### 5.3 Cost of Goods Sold

```text
unit_cost = cost_price + packaging_cost + labeling_cost + shipping_to_warehouse_cost + other_unit_cost
cogs = sold_quantity * unit_cost
```

Use product setting active at `sale_dt` or `rr_date`.

### 5.4 Tax

Support flexible tax model:

```text
NONE: tax = 0
CUSTOM + REVENUE: tax = gross_revenue * tax_rate
CUSTOM + PROFIT: tax = max(profit_before_tax, 0) * tax_rate
USN_INCOME: tax = gross_revenue * tax_rate
USN_PROFIT: tax = max(profit_before_tax, 0) * tax_rate
MANUAL: user-entered tax is applied through external costs or future tax adjustments
```

Do not hard-code legal/tax claims. Let user configure tax mode and rate.

### 5.5 Final values

```text
profit_after_tax = profit_before_tax - tax_amount
profit_margin = profit_after_tax / gross_revenue * 100
return_rate = returned_quantity / max(sold_quantity + returned_quantity, 1) * 100
wb_cost_ratio = wb_costs / max(gross_revenue, 1) * 100
```

---

## 6. Backend API Contract for Future Frontend

### 6.1 Health and diagnostics

```http
GET /api/wb/health/ping?category=finance
GET /api/wb/health/ping?category=content
GET /api/wb/diagnostics/recent
```

### 6.2 Product sync

```http
POST /api/wb/products/sync
GET  /api/wb/products/sync/status
GET  /api/wb/products
GET  /api/wb/products/{product_id}
GET  /api/wb/products/missing-finance-settings
```

`POST /api/wb/products/sync` body:

```json
{
  "mode": "incremental",
  "force_full": false,
  "locale": "ru"
}
```

### 6.3 Seller finance settings

```http
GET /api/finance/settings
PUT /api/finance/settings
```

Body:

```json
{
  "currency": "RUB",
  "defaultTaxMode": "USN_INCOME",
  "defaultTaxRate": 6,
  "taxBase": "REVENUE",
  "defaultPackagingCost": 8,
  "defaultLabelingCost": 3,
  "defaultShippingToWarehouseCost": 0,
  "defaultOtherUnitCost": 0
}
```

### 6.4 Product finance settings

```http
GET  /api/finance/product-settings
GET  /api/finance/product-settings/{product_id}
PUT  /api/finance/product-settings/{product_id}
POST /api/finance/product-settings/import
GET  /api/finance/product-settings/export-template
```

### 6.5 External costs

```http
GET    /api/finance/external-costs
POST   /api/finance/external-costs
PUT    /api/finance/external-costs/{id}
DELETE /api/finance/external-costs/{id}
```

### 6.6 Finance sync

```http
POST /api/finance/reports/sync
GET  /api/finance/reports/sync/status
GET  /api/finance/reports/raw
```

`POST /api/finance/reports/sync` body:

```json
{
  "dateFrom": "2026-03-01",
  "dateTo": "2026-03-31",
  "period": "daily",
  "force": false
}
```

### 6.7 Finance dashboard

```http
GET /api/finance/reports/summary?date_from=2026-03-01&date_to=2026-03-31
GET /api/finance/reports/timeline?date_from=2026-03-01&date_to=2026-03-31&group_by=day
GET /api/finance/reports/products?date_from=2026-03-01&date_to=2026-03-31&sort=profit_after_tax&order=desc
GET /api/finance/reports/cost-breakdown?date_from=2026-03-01&date_to=2026-03-31
GET /api/finance/reports/insights?date_from=2026-03-01&date_to=2026-03-31
```

Summary response shape:

```json
{
  "period": {
    "dateFrom": "2026-03-01",
    "dateTo": "2026-03-31"
  },
  "currency": "RUB",
  "summary": {
    "grossRevenue": "150000.00",
    "forPay": "92000.00",
    "wbCosts": "25600.00",
    "commission": "12000.00",
    "logistics": "8000.00",
    "acquiring": "2600.00",
    "storage": "2000.00",
    "acceptance": "1000.00",
    "penalty": "0.00",
    "deduction": "0.00",
    "additionalPayment": "0.00",
    "costOfGoods": "43000.00",
    "externalCosts": "5000.00",
    "taxAmount": "5520.00",
    "profitBeforeTax": "39000.00",
    "profitAfterTax": "33480.00",
    "profitMargin": "22.32",
    "returnRate": "6.80",
    "soldQuantity": 310,
    "returnedQuantity": 21,
    "missingCostProducts": 12
  }
}
```

### 6.8 Gemini AI analysis

```http
POST /api/finance/ai/analyze
GET  /api/finance/ai/snapshots
GET  /api/finance/ai/snapshots/{id}
```

Body:

```json
{
  "dateFrom": "2026-03-01",
  "dateTo": "2026-03-31",
  "analysisType": "finance_overview",
  "includeProducts": true,
  "maxProducts": 30
}
```

AI input should be aggregated and sanitized. Do not send entire raw rows if there are many rows.

AI output shape:

```json
{
  "summary": "...",
  "risks": [
    {
      "level": "high",
      "title": "Negative profit products",
      "message": "...",
      "affectedProducts": [1234567]
    }
  ],
  "opportunities": [
    {
      "title": "Improve logistics cost",
      "message": "..."
    }
  ],
  "recommendedActions": [
    {
      "priority": 1,
      "action": "Update cost settings for missing products",
      "expectedImpact": "Profit report will become reliable"
    }
  ]
}
```

---

## 7. Implementation Phases

## Phase 0 — Project Audit and Baseline

Goal:

- Understand existing backend structure without breaking current code.

Tasks:

1. Inspect current FastAPI app structure.
2. Inspect existing DB setup, Alembic, config, env handling, tests.
3. Create/update docs:
   - `docs/backend-progress-log.md`
   - `docs/wb-api-field-map.md`
   - `TASKS.md`
4. Add missing dependencies only if needed.
5. Run current tests before changes.

Acceptance:

- Existing tests pass or current failures are documented.
- A short report is appended to `docs/backend-progress-log.md`.

Live test:

- No live WB test yet, except optional `/ping` if tokens are already configured.

---

## Phase 1 — WB Client Foundation and Rate Limiter

Goal:

- Build reliable WB client layer before business logic.

Tasks:

1. Implement `WbBaseClient` using `httpx.AsyncClient`.
2. Implement headers with `Authorization`.
3. Implement structured error handling:
   - `WbApiError`
   - `WbUnauthorizedError`
   - `WbRateLimitError`
   - `WbNoData`
4. Implement rate limiter per category/endpoint:
   - Finance: 1 request/minute for finance report methods.
   - Content: 100 requests/minute, 600ms interval, burst 5.
   - Ping: max 3 requests/30 seconds/host.
5. On `429`, parse `X-Ratelimit-Retry` and `X-Ratelimit-Reset`.
6. Add `api_diagnostic_logs` model and migration.
7. Add client tests with mocked responses.

Acceptance:

- Unit tests pass.
- Rate limiter has tests.
- No token printed in logs.
- Diagnostic log redacts secrets.

Live test:

- Test finance `/ping` if `WB_FINANCE_API_TOKEN` exists.
- Test content `/ping` if `WB_CONTENT_API_TOKEN` exists.
- Append result to `docs/wb-live-test-report.md`.

Report:

- Append Phase 1 report to `docs/backend-progress-log.md`.

---

## Phase 2 — Seller and Token Diagnostics

Goal:

- Verify seller/account identity and token category behavior.

Tasks:

1. Add `sellers` table if not existing.
2. Implement common API client for `GET /api/v1/seller-info`.
3. Save or update default seller from WB response.
4. Add endpoint:
   - `GET /api/wb/health/ping?category=finance|content|common`
   - `GET /api/wb/seller-info`
5. Add tests.

Acceptance:

- Seller can be created/updated from live API.
- Diagnostics do not expose token.

Live test:

- Call seller-info only if token configured and rate limit allows.
- Record `name`, `sid`, `tin`, `tradeMark` if returned.

Report:

- Append Phase 2 report.

---

## Phase 3 — Product Sync MVP

Goal:

- Sync product cards from WB into PostgreSQL before finance reporting.

Tasks:

1. Create migrations:
   - `wb_products`
   - `wb_product_sync_state`
2. Implement `WbContentClient.get_cards_list()`.
3. Implement full product sync:
   - first request: ascending true, cursor limit 100, withPhoto -1.
   - loop until `cursor.total < limit` or no cards.
   - save cursor `updatedAt + nmID`.
4. Implement incremental sync using saved cursor.
5. Upsert products by `(seller_id, nm_id)`.
6. Extract fields:
   - nmID, imtID, nmUUID, subjectID, subjectName, vendorCode, brand, title, description
   - needKiz, kizMarked
   - photos big/square
   - dimensions
   - characteristics JSONB
   - sizes JSONB
   - skus array
   - raw_data JSONB
7. Add endpoints:
   - `POST /api/wb/products/sync`
   - `GET /api/wb/products/sync/status`
   - `GET /api/wb/products`
   - `GET /api/wb/products/{product_id}`
8. Add unit/integration tests.

Acceptance:

- Product sync is idempotent.
- Incremental sync resumes from saved cursor.
- Products are queryable and filterable by nmId, vendorCode, barcode/SKU, title.

Live test:

- Run product sync with real token.
- If many products, stop after first batch in live test unless `WB_LIVE_FULL_PRODUCT_SYNC=1`.
- Verify at least one product inserted or document no data.

Report:

- Append Phase 3 report with:
  - number of products synced
  - cursor saved
  - sample product fields found
  - errors/rate-limit behavior if any

---

## Phase 4 — Finance Settings MVP

Goal:

- Let user provide data WB does not know: cost price, packaging, KIZ/labeling cost, shipping-to-warehouse cost, tax settings.

Tasks:

1. Create migrations:
   - `seller_finance_settings`
   - `product_finance_settings`
   - `external_costs`
2. Implement CRUD services and repositories.
3. Implement endpoint for seller finance settings.
4. Implement endpoint for product finance settings.
5. Implement endpoint to list products missing finance settings.
6. Implement simple import from CSV/XLSX only if project already has upload utilities; otherwise create CSV first and leave XLSX as upgrade.
7. Add validation:
   - cost values >= 0
   - tax rate >= 0
   - effective date ranges cannot overlap for same product
8. Add tests.

Acceptance:

- User can set default tax and default unit costs.
- User can set product-level cost with effective date.
- Product missing cost can be listed.

Live test:

- No WB API required.
- Use synced product from Phase 3 to create test finance settings.

Report:

- Append Phase 4 report.

---

## Phase 5 — Finance Report Sync MVP

Goal:

- Sync raw finance report rows from WB by selected date range.

Tasks:

1. Create migrations:
   - `wb_finance_report_rows`
   - `wb_finance_sync_state`
2. Implement `WbFinanceClient.get_sales_reports_detailed_by_period()`.
3. Implement sync service:
   - input: dateFrom, dateTo, period, force
   - create/update sync state
   - start `rrdId = 0` or resume `last_rrd_id`
   - call API respecting 1 request/minute
   - save rows
   - update `last_rrd_id`
   - stop on `204`
4. Normalize camelCase fields into DB columns.
5. Link finance rows to products by `(seller_id, nm_id)`, fallback by `sku` or `vendorCode` if needed.
6. Store raw JSONB for every row.
7. Add endpoints:
   - `POST /api/finance/reports/sync`
   - `GET /api/finance/reports/sync/status`
   - `GET /api/finance/reports/raw`
8. Add mocked tests for:
   - 200 then 204
   - 429 retry/reschedule behavior
   - duplicate rrdId upsert
   - Decimal parsing from numeric strings

Acceptance:

- Sync is idempotent.
- Sync can resume after failure.
- No duplicate rows.
- Raw and normalized data saved.

Live test:

- Use a very small date range first.
- Request with limited fields first if needed.
- Verify handling of 204/no data.
- Respect 1 request/minute. Do not loop quickly.

Report:

- Append Phase 5 report with:
  - date range tested
  - rows inserted
  - last rrdId
  - status codes
  - sample normalized fields

---

## Phase 6 — Finance Aggregation and Profit Calculation MVP

Goal:

- Turn raw WB rows into useful financial reports.

Tasks:

1. Implement `FinanceAggregationService`.
2. Implement summary aggregation.
3. Implement timeline aggregation by:
   - day
   - week
   - month
   - year
4. Implement product breakdown.
5. Implement cost breakdown.
6. Implement `ProfitCalculationService` using:
   - WB `forPay`
   - product COGS
   - external allocated costs
   - tax settings
7. Add endpoints:
   - `GET /api/finance/reports/summary`
   - `GET /api/finance/reports/timeline`
   - `GET /api/finance/reports/products`
   - `GET /api/finance/reports/cost-breakdown`
8. Add tests with fixtures.

Acceptance:

- Dashboard response does not require frontend to calculate money.
- All money returned as strings or exact decimals serialized safely.
- Missing product cost is reported explicitly.
- Profit fields are clearly named:
  - `profitBeforeTax`
  - `profitAfterTax`
  - `profitMargin`
  - `costCompletenessPercent`

Live test:

- Run aggregation on rows from Phase 5.
- If no finance rows, create local test fixtures and document no live data.

Report:

- Append Phase 6 report and create/update `docs/frontend-contract-report.md`.

---

## Phase 7 — Insights and Alerts MVP

Goal:

- Provide non-AI deterministic insights first.

Tasks:

1. Implement rules:
   - products missing cost settings
   - negative profit products
   - high return rate products
   - high logistics ratio
   - high penalty/deduction products
   - products with revenue but zero/low profit
   - abnormal day cost spike
2. Add endpoint:
   - `GET /api/finance/reports/insights`
3. Add tests.

Acceptance:

- Each insight has:
  - type
  - level: info/warning/danger
  - message
  - affected metric
  - affected product IDs if applicable
  - recommended action

Report:

- Append Phase 7 report.

---

## Phase 8 — Gemini Finance Analysis

Goal:

- Use Gemini to generate business-readable analysis from aggregated finance data.

Tasks:

1. Inspect existing Gemini integration in project.
2. Implement `FinanceAiAnalysisService`.
3. Build sanitized AI payload from:
   - summary
   - cost breakdown
   - top profitable products
   - top loss products
   - missing cost products count
   - deterministic insights
4. Do not send full raw rows unless explicitly enabled.
5. Add endpoint:
   - `POST /api/finance/ai/analyze`
   - `GET /api/finance/ai/snapshots`
6. Store AI result in `finance_analysis_snapshots`.
7. Add fallback if Gemini key missing.
8. Add tests with mocked Gemini client.

Acceptance:

- AI analysis is reproducible enough from saved snapshot.
- Missing Gemini key does not break finance dashboard.
- AI result is JSON structured.

Live test:

- If `GEMINI_API_KEY` exists, run one small analysis using aggregated data.
- Do not send secrets or raw KIZ codes.

Report:

- Append Phase 8 report with sample AI output shape.

---

## Phase 9 — Report List and Reconciliation

Goal:

- Add Sales Report List to compare WB totals with calculated row totals.

Tasks:

1. Implement `POST /api/finance/v1/sales-reports/list` client.
2. Store report list rows in optional table or JSON snapshot.
3. Create reconciliation service:
   - compare `retailAmountSum`
   - compare `forPaySum`
   - compare `deliveryServiceSum`
   - compare `paidStorageSum`
   - compare `paidAcceptanceSum`
   - compare `deductionSum`
   - compare `penaltySum`
   - compare `additionalPaymentSum`
4. Add endpoint:
   - `GET /api/finance/reports/reconciliation`
5. Handle docs note that list may be unavailable in some countries.

Acceptance:

- If API unavailable, backend returns a clean warning, not crash.
- Reconciliation shows differences clearly.

Live test:

- Try one small range.
- Record if API unavailable for seller country.

Report:

- Append Phase 9 report.

---

## Phase 10 — External Costs Advanced Allocation

Goal:

- Improve profit accuracy with monthly shop-level costs.

Tasks:

1. Implement allocation methods:
   - BY_REVENUE
   - BY_SOLD_QUANTITY
   - EQUAL_BY_PRODUCT
   - DIRECT_PRODUCT
2. Add allocated external cost into product breakdown.
3. Add endpoint to preview allocation.
4. Add tests.

Acceptance:

- External cost allocation total equals original amount.
- Product-level allocated costs are explainable.

Report:

- Append Phase 10 report.

---

## Phase 11 — Import/Export for Product Costs

Goal:

- Make it practical for users with many products.

Tasks:

1. Generate CSV/XLSX template:
   - nmId
   - vendorCode
   - sku
   - title
   - costPrice
   - packagingCost
   - labelingCost
   - shippingToWarehouseCost
   - otherUnitCost
   - taxMode
   - taxRate
   - effectiveFrom
2. Implement import with validation preview.
3. Implement confirm import.
4. Add tests.

Acceptance:

- Bad rows are reported with row numbers.
- Valid rows can be imported without corrupting existing settings.

Report:

- Append Phase 11 report.

---

## Phase 12 — Optional Acquiring Detail Upgrade

Goal:

- Add acquiring expense report details if needed for deeper payment cost reconciliation.

Tasks:

1. Implement acquiring list and detailed clients.
2. Add DB tables only if response schema requires separate persistence.
3. Add reconciliation with finance row `acquiringFee`.
4. Handle country restriction cleanly.

Acceptance:

- Feature is optional and does not break MVP.

Report:

- Append Phase 12 report.

---

## Phase 13 — Performance, Indexing, and Frontend Contract Finalization

Goal:

- Make backend stable enough for frontend work.

Tasks:

1. Review SQL queries.
2. Add missing indexes.
3. Add pagination to product and finance product breakdown endpoints.
4. Add OpenAPI tags/descriptions.
5. Generate/update `docs/frontend-contract-report.md` with:
   - all endpoints
   - request params
   - response samples
   - error shapes
   - fields for dashboard cards
   - fields for charts
   - fields for product table
6. Run full test suite.
7. Run mypy/ruff/format if configured.

Acceptance:

- Backend API contract is stable.
- Frontend can be implemented from docs without reading backend internals.

Report:

- Append final backend completion report.

---

## 8. Live Testing Strategy

General rules:

1. Never commit or print real API tokens.
2. Use env variables only.
3. Live tests should be opt-in:

```env
WB_LIVE_TESTS=1
WB_LIVE_FULL_PRODUCT_SYNC=0
WB_LIVE_FULL_FINANCE_SYNC=0
```

4. After every phase, run:

```bash
pytest
```

5. For live tests:

```bash
WB_LIVE_TESTS=1 pytest tests/live/wb -q
```

6. Finance report live tests must respect 1 request/minute.
7. If rate limited, record status and stop instead of retrying aggressively.
8. Append live result to:

```text
docs/wb-live-test-report.md
```

Live report format:

```markdown
## Phase X Live Test - YYYY-MM-DD HH:mm

- Endpoint tested:
- Date range:
- Status codes:
- Rows/products synced:
- Last cursor/rrdId:
- Rate limit headers:
- Errors:
- Conclusion:
```

---

## 9. Task Completion Report Format

After every task or phase, append to:

```text
docs/backend-progress-log.md
```

Format:

```markdown
## Phase X / Task Y - Short Title

### Completed
- ...

### Files changed
- ...

### Tests run
- Command: `...`
- Result: passed/failed

### Live test
- Run: yes/no
- Result: ...

### Notes / Risks
- ...

### Next task
- ...
```

Also update `TASKS.md`:

```markdown
- [x] PHASE-X-TASK-Y: task title
- [ ] PHASE-X-TASK-Z: next task
```

---

## 10. Definition of Done

Backend MVP is done when:

- Product sync works and persists products.
- Product finance settings work.
- Seller finance settings work.
- Finance report sync works by date range.
- Aggregation returns summary/timeline/product/cost breakdown.
- Profit calculation includes WB money, COGS, external costs, and tax settings.
- Deterministic insights work.
- Gemini analysis works with aggregated payload.
- Live tests exist and can run with real WB tokens.
- Frontend contract report exists.
- Tests pass.

Full upgraded backend is done when:

- Sales report list reconciliation exists.
- External cost allocation is advanced.
- Product cost import/export exists.
- Optional acquiring detail module exists or is explicitly documented as skipped.
- Performance/indexing pass is completed.

---

## 12. Notes for Future Frontend Agent

Frontend should wait until backend generates:

```text
docs/frontend-contract-report.md
docs/backend-progress-log.md
docs/wb-live-test-report.md
```

Then frontend can implement:

- Product sync screen.
- Product finance settings screen.
- Seller finance settings screen.
- External costs screen.
- Finance dashboard with cards/charts/tables.
- AI analysis screen.
- Sync status and error diagnostics.

Do not start frontend until backend API contract is stable.
