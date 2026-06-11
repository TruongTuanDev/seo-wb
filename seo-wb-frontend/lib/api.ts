import { FINANCE_ENABLED } from "@/lib/features";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const CSRF_COOKIE_NAME = process.env.NEXT_PUBLIC_CSRF_COOKIE_NAME || "seller_wb_csrf";
const ADMIN_CSRF_COOKIE_NAME = process.env.NEXT_PUBLIC_ADMIN_CSRF_COOKIE_NAME || "seller_wb_admin_csrf";

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

async function fetchWithAuth(url: string, options: ApiOptions = {}) {
  if (!FINANCE_ENABLED && (url === "/finance" || url.startsWith("/finance/") || url.startsWith("/finance?"))) {
    throw new Error("Finance feature is currently unavailable.");
  }

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
    const rawBody = await response.text();
    const contentType = response.headers.get("content-type") || "";
    const isHtmlResponse = contentType.includes("text/html") || /^\s*<!doctype html/i.test(rawBody);
    const fallbackText = rawBody.trim().replace(/\s+/g, " ");
    let errorMsg = isHtmlResponse
      ? `API request failed (${response.status}). The server returned HTML instead of JSON.`
      : fallbackText.slice(0, 500) || response.statusText || "An error occurred";

    try {
      const errorData = JSON.parse(rawBody);
      errorMsg =
        errorData?.error?.message ||
        errorData?.detail?.message ||
        errorData?.detail ||
        errorData?.message ||
        errorMsg;
      const details = errorData?.error?.details || errorData?.details;
      if (details) {
        const detailsText = typeof details === "string" ? details : JSON.stringify(details);
        if (detailsText && detailsText !== "{}" && detailsText !== "null") {
          errorMsg = `${errorMsg}: ${detailsText}`;
        }
      }
    } catch {
      // Keep the raw text because a Response body can only be consumed once.
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
