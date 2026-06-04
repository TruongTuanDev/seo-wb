export function formatMoney(value: string | number | null | undefined, currency = "RUB"): string {
  if (value === null || value === undefined || value === "") return "—";
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "—";
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(num);
}

export function formatPercent(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "—";
  return `${(num * 100).toFixed(1)}%`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export function formatDatetime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function formatRetryAfter(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return "soon";
  if (seconds < 60) return `${Math.ceil(seconds)}s`;
  if (seconds < 3600) return `${Math.ceil(seconds / 60)}m`;
  if (seconds < 86400) {
    const h = Math.floor(seconds / 3600);
    const m = Math.ceil((seconds % 3600) / 60);
    return `${h}h ${m}m`;
  }
  const days = Math.floor(seconds / 86400);
  const hours = Math.ceil((seconds % 86400) / 3600);
  return `${days}d ${hours}h`;
}

export function parseMoney(value: string | null | undefined): number {
  if (!value) return 0;
  return parseFloat(value) || 0;
}

export function isProfitNegative(profitAfterTax: string | null | undefined): boolean {
  return parseMoney(profitAfterTax) < 0;
}

export function formatQuantity(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "—";
  return Math.round(num).toString();
}

export function defaultDateFrom(): string {
  const d = new Date();
  d.setDate(d.getDate() - 7);
  return d.toISOString().slice(0, 10);
}

export function defaultDateTo(): string {
  return new Date().toISOString().slice(0, 10);
}

export function syncStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    idle: "Idle",
    running: "Running",
    completed: "Completed",
    failed: "Failed",
    rate_limited: "Rate Limited",
  };
  return labels[status] ?? status;
}
