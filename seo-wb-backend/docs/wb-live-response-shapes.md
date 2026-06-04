# WB Live Response Shapes

## Scope

This document records only shapes observed from existing live validation evidence already stored in backend reports and diagnostic notes. It does not infer unobserved fields as guaranteed contract. No new live WB call was required for this document.

## Source Evidence

- `docs/wb-live-test-report.md`
- initial diagnostic log summary already captured in progress reports

## Content API `GET /ping`

- Status code observed: `200`
- Sanitized response shape:

```json
{
  "...": "WB ping payload returned and backend treated it as success"
}
```

- Important fields:
  - success was determined by HTTP `200`
- Nullable fields:
  - not documented from live evidence
- Optional or missing fields:
  - full payload shape not captured in the report
- Observed type notes:
  - backend accepts JSON payload
- Rate limit headers observed:
  - no specific live header values recorded
- Cooldown notes:
  - no cooldown recorded for the first successful content ping
- Mapping impact on database schema:
  - none; ping is diagnostic only
- Frontend impact:
  - use as lightweight health probe only if explicitly requested by product UX

## Common API `GET /ping`

- Status code observed: `200`
- Sanitized response shape:

```json
{
  "...": "WB ping payload returned and backend treated it as success"
}
```

- Important fields:
  - success determined by HTTP `200`
- Nullable fields:
  - not documented from live evidence
- Optional or missing fields:
  - full payload shape not captured
- Observed type notes:
  - backend accepts JSON payload
- Rate limit headers observed:
  - no specific live header values recorded
- Cooldown notes:
  - later common seller-info calls hit cooldown, but the initial common ping succeeded
- Mapping impact on database schema:
  - none
- Frontend impact:
  - treat as transport health only, not seller-data freshness

## Finance API `GET /ping`

- Status code observed: `200`
- Sanitized response shape:

```json
{
  "...": "WB ping payload returned and backend treated it as success"
}
```

- Important fields:
  - success determined by HTTP `200`
- Nullable fields:
  - not documented from live evidence
- Optional or missing fields:
  - full payload shape not captured
- Observed type notes:
  - backend accepts JSON payload
- Rate limit headers observed:
  - no specific live header values recorded on the successful ping
- Cooldown notes:
  - finance balance endpoint later entered cooldown, but initial finance ping succeeded
- Mapping impact on database schema:
  - none
- Frontend impact:
  - transport-only health signal

## Common API `GET /api/v1/seller-info`

- Status code observed: `200` on first successful call
- Sanitized response shape:

```json
{
  "name": "string",
  "sid": "string or number",
  "tin": "string",
  "tradeMark": "string"
}
```

- Important fields:
  - `name`
  - `sid`
  - `tin`
  - `tradeMark`
- Nullable fields:
  - not confirmed from live evidence
- Optional or missing fields:
  - only the fields above were explicitly observed and recorded
- Observed type notes:
  - `sid` may be string-like or numeric depending on WB serialization
- Rate limit headers observed:
  - later `429` response included `X-Ratelimit-Retry=86367`
- Cooldown notes:
  - repeated follow-up call hit strict cooldown after the initial success
- Mapping impact on database schema:
  - maps into seller metadata fields such as `externalSid`, `name`, `tradeMark`, `tin`
- Frontend impact:
  - seller identity screen should tolerate partial seller metadata
  - do not poll aggressively because this endpoint can enter long cooldown

## Content API `POST /content/v2/get/cards/list`

- Status code observed: `200`
- Sanitized response shape from observed sample:

```json
{
  "cards": [
    {
      "nmID": 1022471872,
      "imtID": 1991018770,
      "vendorCode": "D8013-XANH",
      "subjectName": "Шорты"
    }
  ],
  "cursor": {
    "updatedAt": "datetime string",
    "nmID": 1022471872,
    "total": 1
  }
}
```

- Important fields:
  - `cards[*].nmID`
  - `cards[*].imtID`
  - `cards[*].vendorCode`
  - `cards[*].subjectName`
  - `cursor.updatedAt`
  - `cursor.nmID`
  - `cursor.total`
- Nullable fields:
  - product descriptive fields may be absent or null depending on card completeness
- Optional or missing fields:
  - full card body was not fully recorded in the live report
- Observed type notes:
  - `nmID` and `imtID` are numeric identifiers
  - `vendorCode` and `subjectName` are strings
- Rate limit headers observed:
  - no specific live header values recorded on the successful sample request
- Cooldown notes:
  - no content cards-list cooldown was recorded in the existing live report
- Mapping impact on database schema:
  - `nmID` -> `wb_products.nm_id`
  - `imtID` -> `wb_products.imt_id`
  - `vendorCode` -> `wb_products.vendor_code`
  - `subjectName` -> `wb_products.subject_name`
  - full raw card -> `wb_products.raw_data`
  - cursor fields -> `wb_product_sync_state`
- Frontend impact:
  - product sync UI can trust `nmId` as the primary WB product identity
  - cursor-driven incremental sync should be treated as backend-owned state

## Finance API `GET /api/v1/account/balance`

- Status code observed: `200` on first successful call
- Sanitized response shape:

```json
{
  "...": "balance payload succeeded but exact field list was not preserved in the public report"
}
```

- Important fields:
  - successful account balance access was confirmed
- Nullable fields:
  - not documented from live evidence
- Optional or missing fields:
  - full payload keys were not recorded in the report
- Observed type notes:
  - backend accepted JSON payload
- Rate limit headers observed:
  - later `429` response included `X-Ratelimit-Retry=86366`
- Cooldown notes:
  - follow-up balance call hit near-day cooldown
- Mapping impact on database schema:
  - none in current finance reporting schema; this endpoint is diagnostic only
- Frontend impact:
  - do not depend on this endpoint for the finance dashboard MVP

## Finance Detailed Report

- Live validation status: not live validated yet in the documented evidence set for this stabilization phase
- Backend readiness:
  - sync logic exists
  - `rrdId` pagination exists
  - duplicate prevention exists
  - JSONB raw row storage exists
  - test coverage exists for multi-page sync, `204` stop, resume, duplicate handling, and cooldown path
- Mapping impact on database schema:
  - detailed rows map into `wb_finance_report_rows`
  - row-to-product linkage uses `nmId`, `sku`, then `vendorCode`
- Frontend impact:
  - frontend can build against the backend response contract
  - treat some raw-field variability as unconfirmed until a safe future live validation is performed

## Rate Limit Header Observations Summary

- Observed headers from cooldown responses:
  - `X-Ratelimit-Retry`
- Supported by backend parser and recorded safely when present:
  - `X-Ratelimit-Retry`
  - `X-Ratelimit-Reset`
  - `X-Ratelimit-Limit`
  - `X-Ratelimit-Remaining`
  - `Retry-After`

## Cooldown Behavior Summary

- First successful calls do not guarantee repeated availability.
- Existing live evidence shows WB may return long cooldown windows close to one day.
- Backend now blocks repeated requests locally while cooldown remains active.
- Frontend should read `GET /api/v1/finance/system-status` before encouraging retry-heavy actions.
