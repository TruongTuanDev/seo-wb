# WB API Field Map

## Finance Detailed Report

- Source endpoint planned: `POST /api/finance/v1/sales-reports/detailed`
- Source naming convention: camelCase fields from the modern finance API
- Persistence rule: keep normalized columns for reporting and store the full raw row in JSONB
- Normalized identifiers:
  `reportId -> report_id`, `rrdId -> rrd_id`, `nmId -> nm_id`, `vendorCode -> vendor_code`, `sku -> sku`
- Normalized money fields:
  `retailAmount`, `forPay`, `deliveryService`, `ppvzSalesCommission`, `acquiringFee`, `penalty`, `deduction`, `paidStorage`, `paidAcceptance`, `additionalPayment`, `rebillLogisticCost`, `agencyVat`
- Normalized date/time fields:
  `dateFrom`, `dateTo`, `createDate`, `orderDt`, `saleDt`, `rrDate`

## Product Card Sync

- Source endpoint reused: `POST /content/v2/get/cards/list`
- Persistence rule: keep product identifiers, searchable fields, photo URLs, dimensions, sizes, SKUs, characteristics, and full raw payload
- Product key mapping:
  `nmID/nmId -> nm_id`, `imtID/imtId -> imt_id`, `subjectID/subjectId -> subject_id`, `subjectName -> subject_name`, `vendorCode -> vendor_code`
- Search mapping fallback order for finance rows:
  `(seller_id, nm_id)` then `sku` then `vendor_code`

## Notes

- Do not mix deprecated snake_case statistics fields into the primary finance persistence model.
- Mapping will be expanded as finance sync and aggregation modules are implemented.
