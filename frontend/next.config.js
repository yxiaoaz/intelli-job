/** @type {import('next').NextConfig} */
const nextConfig = {
  // ⚠️ EdgeOne Makers 不支持 next.config.js rewrites，使用 edgeone.json 替代
  // 此处的 rewrites 仅供本地开发（next dev）和 Vercel 使用
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/:path*`,
      },
    ];
  },
}

module.exports = nextConfig
