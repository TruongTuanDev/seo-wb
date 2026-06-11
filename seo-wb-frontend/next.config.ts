import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    if (process.env.NEXT_PUBLIC_ENABLE_FINANCE === "true") {
      return [];
    }

    return [
      { source: "/finance/:path*", destination: "/", permanent: false },
      { source: "/financial/:path*", destination: "/", permanent: false },
      { source: "/financial-management/:path*", destination: "/", permanent: false },
      { source: "/finance-management/:path*", destination: "/", permanent: false },
      { source: "/finance-reports/:path*", destination: "/", permanent: false },
      { source: "/analytics/finance/:path*", destination: "/", permanent: false },
      { source: "/analytics/financial/:path*", destination: "/", permanent: false },
      { source: "/reports/finance/:path*", destination: "/", permanent: false },
      { source: "/reports/financial/:path*", destination: "/", permanent: false },
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
