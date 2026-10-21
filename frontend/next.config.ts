import type { NextConfig } from "next";

// Where the Flask API runs. The browser never talks to it directly: every
// request to /api/* on this site is forwarded there (same-origin, so the
// HttpOnly refresh cookie and CSRF header work without CORS).
const apiUrl = (process.env.ASZDA_API_URL || "http://localhost:5000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  // Cache Components is left off on purpose: almost every app screen is
  // rendered in the browser behind sign-in, so it adds complexity without benefit.
  poweredByHeader: false,
  // Do not let `next dev` (re)create AGENTS.md in this folder.
  agentRules: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
