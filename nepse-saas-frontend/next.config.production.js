/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable React Strict Mode
  reactStrictMode: true,

  // For Azure Static Web Apps - static export
  output: process.env.BUILD_MODE === 'static' ? 'export' : undefined,
  trailingSlash: true,

  // Required for static export
  images: {
    unoptimized: process.env.BUILD_MODE === 'static',
  },

  // Environment variables exposed to browser
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },

  // API proxy to FastAPI backend (only works in non-static mode)
  async rewrites() {
    // Skip rewrites for static export
    if (process.env.BUILD_MODE === 'static') {
      return [];
    }
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
