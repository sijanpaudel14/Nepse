/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',  // Enable static export
  reactStrictMode: true,
  trailingSlash: true,
  images: {
    unoptimized: true  // Required for static export
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'https://api.nepse.sijanpaudel.com.np'
  }
};

export default nextConfig;