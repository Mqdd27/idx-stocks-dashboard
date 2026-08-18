/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8200/api/:path*",
      },
      {
        source: "/health",
        destination: "http://127.0.0.1:8200/health",
      },
    ];
  },
};

export default nextConfig;