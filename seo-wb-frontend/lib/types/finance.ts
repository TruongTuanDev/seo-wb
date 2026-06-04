export interface CooldownInfo {
  sellerId: number;
  category: string;
  host: string;
  method: string;
  endpoint: string;
  retryAfterSeconds: number;
  source: string;
  headers: Record<string, string | null>;
}

export interface ApiStatusBlock {
  available: boolean;
  inCooldown: boolean;
  activeCooldownCount: number;
  cooldowns: CooldownInfo[];
}

export interface FinanceSystemStatus {
  contentApi: ApiStatusBlock;
  financeApi: ApiStatusBlock;
  commonApi: ApiStatusBlock;
  sellerInfoApi: ApiStatusBlock;
  activeCooldowns: CooldownInfo[];
  lastSuccessfulProductSyncAt: string | null;
  lastSuccessfulFinanceSyncAt: string | null;
  lastFailedSyncAt: string | null;
  lastFailedSyncError: string | null;
  geminiConfigured: boolean;
  hasProductsMissingFinanceSettings: boolean;
  missingFinanceSettingsCount: number;
  hasUnmappedFinanceRows: boolean;
  unmappedFinanceRowsCount: number;
  automationTimezone: string | null;
  bootstrapStatus: string | null;
  bootstrapRangeFrom: string | null;
  bootstrapRangeTo: string | null;
  bootstrapFinishedAt: string | null;
  lastSuccessfulDailySyncDate: string | null;
  lastDailySyncStatus: string | null;
  lastDailySyncError: string | null;
  nextScheduledRunAt: string | null;
}

export interface FinancePeriod {
  dateFrom: string;
  dateTo: string;
}

export interface FinanceSummary {
  period: FinancePeriod;
  grossRevenue: string;
  forPay: string;
  wbCosts: string;
  cogs: string;
  externalAllocatedCosts: string;
  profitBeforeTax: string;
  taxAmount: string;
  profitAfterTax: string;
  profitMargin: string;
  costCompletenessPercent: string;
  rowsCount: number;
  productsCount: number;
}

export interface FinanceTimelinePoint {
  bucket: string;
  forPay: string;
  grossRevenue: string;
  profitAfterTax: string;
}

export interface FinanceTimelineResponse {
  items: FinanceTimelinePoint[];
}

export interface ProductCostMeta {
  costPrice: string;
  packagingCost: string;
  labelingCost: string;
  shippingToWarehouseCost: string;
  otherUnitCost: string;
}

export interface FinanceProductBreakdownItem {
  productId: number | null;
  nmId: number | null;
  vendorCode: string | null;
  title: string | null;
  quantity: string;
  grossRevenue: string;
  forPay: string;
  wbCosts: string;
  cogs: string;
  externalAllocatedCosts: string;
  profitBeforeTax: string;
  taxAmount: string;
  profitAfterTax: string;
  profitMargin: string;
  hasCostSettings: boolean;
  costMeta: ProductCostMeta | null;
}

export interface FinanceProductBreakdownResponse {
  items: FinanceProductBreakdownItem[];
  page: number;
  perPage: number;
  total: number;
}

export interface FinanceCostBreakdown {
  wbCosts: string;
  cogs: string;
  externalAllocatedCosts: string;
}

export interface FinanceInsight {
  type: string;
  level: "info" | "warning" | "danger";
  message: string;
  affectedMetric: string;
  productIds: number[];
  recommendedAction: string;
}

export interface FinanceInsightsResponse {
  items: FinanceInsight[];
}

export type SyncStatus = "idle" | "running" | "completed" | "failed" | "rate_limited" | string;

export interface FinanceSyncStatus {
  status: SyncStatus;
  lastRrdId: number | null;
  totalRows: number | null;
  lastError: string | null;
}

export interface FinanceSyncResponse {
  status: SyncStatus;
  rowsInserted: number;
  lastRrdId: number | null;
}

export interface ProductSyncStatus {
  status: SyncStatus;
  cursorUpdatedAt: string | null;
  cursorNmId: number | null;
  totalSynced: number | null;
  lastError: string | null;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface ProductSyncResponse {
  status: SyncStatus;
  totalSynced: number;
  cursorUpdatedAt: string | null;
  cursorNmId: number | null;
  batches: number;
}

export interface ProductFinanceSetting {
  id: number;
  sellerId: number;
  productId: number;
  costPrice: string;
  costCurrency: string;
  packagingCost: string;
  labelingCost: string;
  shippingToWarehouseCost: string;
  otherUnitCost: string;
  taxMode: string;
  taxRate: string;
  taxBase: string;
  effectiveFrom: string | null;
  effectiveTo: string | null;
  note: string | null;
}

export interface ProductFinanceSettingsResponse {
  items: ProductFinanceSetting[];
  page: number;
  perPage: number;
  total: number;
}

export interface ProductFinanceCatalogItem {
  productId: number;
  nmId: number;
  vendorCode: string | null;
  title: string | null;
  subjectName: string | null;
  brand: string | null;
  photoSquareUrl: string | null;
  photoBigUrl: string | null;
  hasCostSettings: boolean;
  settingId: number | null;
  costPrice: string | null;
  costCurrency: string | null;
  packagingCost: string | null;
  labelingCost: string | null;
  shippingToWarehouseCost: string | null;
  otherUnitCost: string | null;
  taxMode: string | null;
  taxRate: string | null;
  taxBase: string | null;
  effectiveFrom: string | null;
  effectiveTo: string | null;
  note: string | null;
}

export interface ProductFinanceCatalogFacets {
  brands: string[];
  subjects: string[];
}

export interface ProductFinanceCatalogResponse {
  items: ProductFinanceCatalogItem[];
  page: number;
  perPage: number;
  total: number;
  facets: ProductFinanceCatalogFacets;
}

export interface SellerFinanceSettings {
  id: number;
  sellerId: number;
  currency: string;
  defaultTaxMode: string;
  defaultTaxRate: string;
  taxBase: string;
  defaultPackagingCost: string;
  defaultLabelingCost: string;
  defaultShippingToWarehouseCost: string;
  defaultOtherUnitCost: string;
}

export interface ExternalCost {
  id: number;
  sellerId: number;
  costDate: string;
  periodFrom: string;
  periodTo: string;
  costType: string;
  amount: string;
  currency: string;
  allocationMethod: string;
  productId: number | null;
  note: string | null;
}

export interface ExternalCostsResponse {
  items: ExternalCost[];
  page: number;
  perPage: number;
  total: number;
}

export interface GeminiAnalysisResult {
  summary: string;
  insights: unknown[];
}

export interface GeminiFinanceAnalysis {
  snapshotId: number;
  analysis: GeminiAnalysisResult;
}

export interface GeminiSnapshotItem {
  id: number;
  dateFrom: string;
  dateTo: string;
  aiAnalysis: {
    summary: string;
  };
}

export interface GeminiSnapshotsResponse {
  items: GeminiSnapshotItem[];
}

export interface MissingSettingsProduct {
  id: number;
  nmId: number;
  vendorCode: string;
  title: string;
}

export interface MissingSettingsResponse {
  items: MissingSettingsProduct[];
}

export interface WbProduct {
  id: number;
  nmId: number | null;
  imtId: number | null;
  vendorCode: string | null;
  brand: string | null;
  title: string | null;
  description: string | null;
  subjectId: number | null;
  subjectName: string | null;
  photoBigUrl: string | null;
  photoSquareUrl: string | null;
  sizes: unknown[];
  skus: string[];
  characteristics: unknown[];
  rawData: Record<string, unknown>;
  wbUpdatedAt: string | null;
}

export interface WbProductsResponse {
  items: WbProduct[];
  page: number;
  perPage: number;
  total: number;
}

export interface ReconciliationReportListTotals {
  retailAmountSum: string;
  forPaySum: string;
  deliveryServiceSum: string;
}

export interface ReconciliationResponse {
  warning: string | null;
  calculatedSummary: FinanceSummary;
  reportListCount: number;
  reportListTotals: ReconciliationReportListTotals;
  differences: ReconciliationReportListTotals;
}

export type GroupBy = "day" | "week" | "month" | "year";

export interface AllocationPreviewItem {
  productId: number;
  nmId: number;
  vendorCode: string;
  allocatedAmount: string;
}

export interface AllocationPreviewResponse {
  items: AllocationPreviewItem[];
}

export interface SettingsImportResponse {
  imported: number;
  errors: Array<{ row: number; error: string }>;
}
