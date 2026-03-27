/** @type {import('next').NextConfig} */
const isStaticBuild = process.env.BUILD_MODE === 'static'

const nextConfig = {
  // Static export only when explicitly building for Azure Storage
  // Vercel uses full Next.js build (no output: 'export' needed)
  ...(isStaticBuild ? { output: 'export' } : {}),
  reactStrictMode: true,
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL ||
      'https://nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io',
  },
}

module.exports = nextConfig
