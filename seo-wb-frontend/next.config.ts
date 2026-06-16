import type { NextConfig } from "next";

function backendPublicPath(path: string) {
  const apiUrl = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
  const absoluteApiUrl = apiUrl.startsWith("/") ? "http://localhost:8000/api/v1" : apiUrl;
  const base = absoluteApiUrl.replace(/\/+$/, "").replace(/\/api\/v\d+$/i, "").replace(/\/api$/i, "");
  return `${base}${path}`;
}

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/storage/:path*",
        destination: backendPublicPath("/storage/:path*"),
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
