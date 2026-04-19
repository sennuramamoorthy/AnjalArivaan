/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // DPDP: data-residency-friendly. No external analytics, no telemetry.
  experimental: {
    typedRoutes: false,
  },
  async rewrites() {
    // Let the Next frontend proxy API calls to the FastAPI backend in dev / prod.
    const api = process.env.BACKEND_INTERNAL_URL || "http://backend:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${api}/api/v1/:path*`,
      },
      {
        source: "/healthz",
        destination: `${api}/healthz`,
      },
    ];
  },
};

module.exports = nextConfig;
