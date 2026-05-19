import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 开发阶段代理后端请求，解决跨域问题
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
