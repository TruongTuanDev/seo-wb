import { api, API_BASE } from "./api";
import type {
  FinanceSystemStatus,
  FinanceSummary,
  FinanceTimelineResponse,
  FinanceProductBreakdownResponse,
  FinanceCostBreakdown,
  FinanceInsightsResponse,
  FinanceSyncResponse,
  FinanceSyncStatus,
  ProductSyncResponse,
  ProductSyncStatus,
  ProductFinanceCatalogResponse,
  SellerFinanceSettings,
  ProductFinanceSettingsResponse,
  ExternalCost,
  ExternalCostsResponse,
  GeminiFinanceAnalysis,
  GeminiSnapshotsResponse,
  MissingSettingsResponse,
  WbProductsResponse,
  ReconciliationResponse,
  GroupBy,
  AllocationPreviewResponse,
  SettingsImportResponse,
} from "./types/finance";

function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined && v !== "") {
      p.set(k, String(v));
    }
  }
  const str = p.toString();
  return str ? `?${str}` : "";
}

export const financeApi = {
  getSystemStatus: (storeId: number): Promise<FinanceSystemStatus> =>
    api.get(`/finance/system-status?store_id=${storeId}`),

  triggerProductSync: (storeId: number, full = false): Promise<ProductSyncResponse> =>
    api.post(`/wb/products/sync?store_id=${storeId}&full=${full}`),

  getProductSyncStatus: (storeId: number): Promise<ProductSyncStatus> =>
    api.get(`/wb/products/sync/status?store_id=${storeId}`),

  getWbProducts: (
    storeId: number,
    params?: { nmId?: string; vendorCode?: string; sku?: string; title?: string; brand?: string; subjectName?: string; page?: number; perPage?: number }
  ): Promise<WbProductsResponse> =>
    api.get(`/wb/products${qs({ store_id: storeId, ...params })}`),

  triggerFinanceSync: (
    storeId: number,
    body: { date_from: string; date_to: string; period?: string; force?: boolean }
  ): Promise<FinanceSyncResponse> =>
    api.post(`/finance/reports/sync?store_id=${storeId}`, body),

  getFinanceSyncStatus: (
    storeId: number,
    params?: { date_from?: string; date_to?: string; period?: string }
  ): Promise<FinanceSyncStatus> =>
    api.get(`/finance/reports/sync/status${qs({ store_id: storeId, ...params })}`),

  getSummary: (storeId: number, dateFrom: string, dateTo: string): Promise<FinanceSummary> =>
    api.get(`/finance/reports/summary?store_id=${storeId}&date_from=${dateFrom}&date_to=${dateTo}`),

  getTimeline: (storeId: number, dateFrom: string, dateTo: string, groupBy: GroupBy): Promise<FinanceTimelineResponse> =>
    api.get(`/finance/reports/timeline?store_id=${storeId}&date_from=${dateFrom}&date_to=${dateTo}&group_by=${groupBy}`),

  getProductBreakdown: (
    storeId: number,
    params: { date_from: string; date_to: string; page?: number; perPage?: number; sort?: string; order?: string }
  ): Promise<FinanceProductBreakdownResponse> =>
    api.get(`/finance/reports/products${qs({ store_id: storeId, ...params })}`),

  getCostBreakdown: (storeId: number, dateFrom: string, dateTo: string): Promise<FinanceCostBreakdown> =>
    api.get(`/finance/reports/cost-breakdown?store_id=${storeId}&date_from=${dateFrom}&date_to=${dateTo}`),

  getInsights: (storeId: number, dateFrom: string, dateTo: string): Promise<FinanceInsightsResponse> =>
    api.get(`/finance/reports/insights?store_id=${storeId}&date_from=${dateFrom}&date_to=${dateTo}`),

  getReconciliation: (
    storeId: number,
    dateFrom: string,
    dateTo: string,
    period = "daily"
  ): Promise<ReconciliationResponse> =>
    api.get(`/finance/reports/reconciliation?store_id=${storeId}&date_from=${dateFrom}&date_to=${dateTo}&period=${period}`),

  getSellerSettings: (storeId: number): Promise<SellerFinanceSettings> =>
    api.get(`/finance/settings?store_id=${storeId}`),

  updateSellerSettings: (
    storeId: number,
    body: Record<string, string | number | null>
  ): Promise<SellerFinanceSettings> =>
    api.put(`/finance/settings?store_id=${storeId}`, body),

  getProductSettings: (
    storeId: number,
    params?: { page?: number; perPage?: number }
  ): Promise<ProductFinanceSettingsResponse> =>
    api.get(`/finance/product-settings${qs({ store_id: storeId, ...params })}`),

  getProductSettingsCatalog: (
    storeId: number,
    params?: {
      page?: number;
      perPage?: number;
      search?: string;
      brands?: string[];
      subjects?: string[];
      onlyMissing?: boolean;
    }
  ): Promise<ProductFinanceCatalogResponse> => {
    const query = new URLSearchParams();
    query.set("store_id", String(storeId));
    if (params?.page) query.set("page", String(params.page));
    if (params?.perPage) query.set("per_page", String(params.perPage));
    if (params?.search) query.set("search", params.search);
    if (params?.onlyMissing) query.set("onlyMissing", "true");
    for (const brand of params?.brands || []) {
      query.append("brands", brand);
    }
    for (const subject of params?.subjects || []) {
      query.append("subjects", subject);
    }
    return api.get(`/finance/product-settings/catalog?${query.toString()}`);
  },

  getProductSettingsById: (
    storeId: number,
    productId: number
  ): Promise<ProductFinanceSettingsResponse> =>
    api.get(`/finance/product-settings/${productId}?store_id=${storeId}`),

  updateProductSetting: (
    storeId: number,
    productId: number,
    body: Record<string, string | number | null>
  ): Promise<ProductFinanceSettingsResponse> =>
    api.put(`/finance/product-settings/${productId}?store_id=${storeId}`, body),

  updateProductSettingsBulk: (
    storeId: number,
    items: Array<{ product_id: number; cost_price: string | number }>
  ): Promise<ProductFinanceSettingsResponse[]> =>
    api.put(`/finance/product-settings/bulk?store_id=${storeId}`, { items }).then((response) => response.items),

  getMissingSettings: (storeId: number): Promise<MissingSettingsResponse> =>
    api.get(`/finance/products/missing-settings?store_id=${storeId}`),

  getExportTemplateUrl: (storeId: number, mode: "prepared" | "sample" = "prepared"): string =>
    `${API_BASE}/finance/product-settings/export-template?store_id=${storeId}&mode=${mode}`,

  importSettings: (storeId: number, file: File): Promise<SettingsImportResponse> => {
    const form = new FormData();
    form.append("file", file);
    return api.post(`/finance/product-settings/import?store_id=${storeId}`, form);
  },

  getExternalCosts: (
    storeId: number,
    params?: { page?: number; perPage?: number }
  ): Promise<ExternalCostsResponse> =>
    api.get(`/finance/external-costs${qs({ store_id: storeId, ...params })}`),

  createExternalCost: (
    storeId: number,
    body: Record<string, string | number | null>
  ): Promise<ExternalCost> =>
    api.post(`/finance/external-costs?store_id=${storeId}`, body),

  updateExternalCost: (
    storeId: number,
    id: number,
    body: Record<string, string | number | null>
  ): Promise<ExternalCost> =>
    api.put(`/finance/external-costs/${id}?store_id=${storeId}`, body),

  deleteExternalCost: (storeId: number, id: number): Promise<null> =>
    api.delete(`/finance/external-costs/${id}?store_id=${storeId}`),

  getExternalCostAllocationPreview: (
    storeId: number,
    dateFrom: string,
    dateTo: string
  ): Promise<AllocationPreviewResponse> =>
    api.get(
      `/finance/external-costs/preview-allocation?store_id=${storeId}&date_from=${dateFrom}&date_to=${dateTo}`
    ),

  analyzeWithGemini: (
    storeId: number,
    body: { date_from: string; date_to: string; group_by: GroupBy }
  ): Promise<GeminiFinanceAnalysis> =>
    api.post(`/finance/ai/analyze?store_id=${storeId}`, body),

  getGeminiSnapshots: (storeId: number): Promise<GeminiSnapshotsResponse> =>
    api.get(`/finance/ai/snapshots?store_id=${storeId}`),
};
