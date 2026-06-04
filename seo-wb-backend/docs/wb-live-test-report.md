# WB Live Test Report

No live WB API test has been run for the finance module yet.

## 2026-05-18

- Live tests were skipped because `WB_LIVE_TESTS` was not enabled in the current shell and no explicit `WB_CONTENT_API_TOKEN`, `WB_FINANCE_API_TOKEN`, or `WB_COMMON_API_TOKEN` environment variables were present.
- No read-only WB API call was executed in this rollout.

## 2026-05-18 15:42:55 +07:00

- Live token provided manually for direct backend probe. Token value is intentionally not stored in this report.
- Successful read-only probes:
  - `GET content /ping` -> `200`
  - `GET common /ping` -> `200`
  - `GET finance /ping` -> `200`
  - `GET common /api/v1/seller-info` -> `200` on the first successful attempt recorded in diagnostic logs
  - `POST content /content/v2/get/cards/list` with cursor limit `1` -> `200`
  - `GET finance /api/v1/account/balance` -> `200` on the first successful attempt recorded in diagnostic logs
- Safe seller fields observed from the successful seller-info call:
  - `name`, `sid`, `tin`, `tradeMark` were returned by WB
- Sample synced-content fields observed from the successful cards-list call:
  - `nmID=1022471872`
  - `imtID=1991018770`
  - `vendorCode=D8013-XANH`
  - `subjectName=Шорты`
- Live blocker encountered immediately after the first successful common/finance detail probes:
  - file: `app/services/wb_base_client.py`
  - command: direct `.venv` Python probe using `WbCommonClient.get_seller_info()`, `WbContentClient.get_cards_list(limit=1)`, and `WbFinanceClient.get_balance()`
  - error: WB returned `429 Too Many Requests` for `GET /api/v1/seller-info` with `X-Ratelimit-Retry=86367` and for `GET /api/v1/account/balance` with `X-Ratelimit-Retry=86366`
  - likely cause: WB applies strict server-side cooldown on those common/finance endpoints for this seller/token, and repeated calls too soon trigger a near-day retry window
  - proposed fix: stop live calls on first `429`, persist cooldown locally per endpoint, and retry only after the server-provided reset window
- Code fix applied after the live test:
  - `WbBaseClient` now records endpoint-level cooldown after server `429` and blocks immediate repeat calls locally before they hit WB again
- Validation after fix:
  - `python -m pytest` -> `21 passed`
