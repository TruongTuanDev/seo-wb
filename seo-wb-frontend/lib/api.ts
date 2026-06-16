export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const CSRF_COOKIE_NAME = process.env.NEXT_PUBLIC_CSRF_COOKIE_NAME || "seller_wb_csrf";
const ADMIN_CSRF_COOKIE_NAME = process.env.NEXT_PUBLIC_ADMIN_CSRF_COOKIE_NAME || "seller_wb_admin_csrf";

export function publicAssetUrl(url: string | null | undefined) {
  if (!url) return "";
  if (/^https?:\/\//i.test(url) || url.startsWith("data:") || url.startsWith("blob:")) {
    return url;
  }
  if (!url.startsWith("/storage")) {
    return url;
  }
  return `${apiPublicOrigin()}${url}`;
}

function apiPublicOrigin() {
  const cleanBase = API_BASE.replace(/\/+$/, "");
  if (cleanBase.startsWith("/")) {
    if (typeof window !== "undefined" && window.location.hostname === "localhost" && window.location.port === "3030") {
      return "http://localhost:8000";
    }
    return "";
  }
  try {
    const parsed = new URL(cleanBase);
    parsed.pathname = parsed.pathname.replace(/\/api\/v\d+$/i, "").replace(/\/api$/i, "");
    parsed.search = "";
    parsed.hash = "";
    return parsed.toString().replace(/\/+$/, "");
  } catch {
    return cleanBase.replace(/\/api\/v\d+$/i, "").replace(/\/api$/i, "");
  }
}

interface ApiOptions extends RequestInit {
  requireAuth?: boolean;
  redirectOnUnauthorized?: boolean;
  authScope?: "user" | "admin";
}

function readCookie(name: string) {
  if (typeof document === "undefined") return null;
  return document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${name}=`))
    ?.split("=")[1] || null;
}

function formatApiError(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    const messages = value
      .map((item) => {
        if (!item || typeof item !== "object") return String(item || "");
        const detail = item as { loc?: unknown[]; msg?: unknown; message?: unknown };
        const location = Array.isArray(detail.loc)
          ? detail.loc.filter((part) => part !== "body").join(".")
          : "";
        const message = String(detail.msg || detail.message || "").trim();
        if (!message) return "";
        return location ? `${location}: ${message}` : message;
      })
      .filter(Boolean);
    return messages.join("; ");
  }
  if (value && typeof value === "object") {
    const detail = value as { message?: unknown; msg?: unknown };
    const message = detail.message || detail.msg;
    if (typeof message === "string") return message;
    try {
      return JSON.stringify(value);
    } catch {
      return "An error occurred";
    }
  }
  return value == null ? "" : String(value);
}

async function fetchWithAuth(url: string, options: ApiOptions = {}) {
  const { requireAuth = true, redirectOnUnauthorized = true, authScope, headers, ...rest } = options;

  const finalHeaders = new Headers(headers);
  const method = (rest.method || "GET").toString().toUpperCase();
  const scope = authScope || (url.startsWith("/admin") ? "admin" : "user");
  const csrfToken = readCookie(scope === "admin" ? ADMIN_CSRF_COOKIE_NAME : CSRF_COOKIE_NAME);
  if (csrfToken && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    finalHeaders.set("X-CSRF-Token", decodeURIComponent(csrfToken));
  }

  // If body is FormData, don't set Content-Type so the browser sets it with the boundary
  if (!(options.body instanceof FormData)) {
    if (!finalHeaders.has("Content-Type") && options.body) {
       finalHeaders.set("Content-Type", "application/json");
    }
  }

  const response = await fetch(`${API_BASE}${url}`, {
    ...rest,
    headers: finalHeaders,
    credentials: "include",
  });

  if (!response.ok) {
    if (response.status === 401 && requireAuth && redirectOnUnauthorized && typeof window !== "undefined") {
      window.location.href = "/login";
    }
    let errorMsg = "An error occurred";
    const responseText = await response.text();
    try {
      const errorData = JSON.parse(responseText);
      errorMsg = formatApiError(
        errorData?.error?.message ||
        errorData?.detail?.message ||
        errorData?.detail ||
        errorData?.message ||
        errorData
      ) || "An error occurred";
      const details = errorData?.error?.details || errorData?.details;
      if (details) {
        const detailsText = typeof details === "string" ? details : JSON.stringify(details);
        if (detailsText && detailsText !== "{}" && detailsText !== "null") {
          errorMsg = `${errorMsg}: ${detailsText}`;
        }
      }
    } catch {
      errorMsg = responseText || response.statusText;
    }
    throw new Error(errorMsg);
  }

  // Return null for 204 No Content
  if (response.status === 204) {
      return null;
  }

  // Some endpoints might return text instead of json
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    return response.json();
  }
  
  return response.text();
}

export const api = {
  get: (url: string, options?: ApiOptions) => fetchWithAuth(url, { ...options, method: "GET" }),
  post: (url: string, body?: unknown, options?: ApiOptions) =>
    fetchWithAuth(url, { 
      ...options, 
      method: "POST", 
      body: body instanceof FormData ? body : JSON.stringify(body) 
    }),
  put: (url: string, body?: unknown, options?: ApiOptions) =>
    fetchWithAuth(url, { 
       ...options, 
       method: "PUT", 
       body: body instanceof FormData ? body : JSON.stringify(body) 
    }),
  patch: (url: string, body?: unknown, options?: ApiOptions) =>
    fetchWithAuth(url, {
       ...options,
       method: "PATCH",
    body: body instanceof FormData ? body : JSON.stringify(body) 
    }),
  delete: (url: string, options?: ApiOptions) => fetchWithAuth(url, { ...options, method: "DELETE" }),
};
