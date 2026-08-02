/** @type {import('next').NextConfig} */
const nextConfig = {
  // ⚠️ EdgeOne Makers 不支持 next.config.js rewrites，使用 edgeone.json 替代
  // 此处的 rewrites 仅供本地开发（next dev）和 Vercel 使用
  // 当 NEXT_PUBLIC_API_URL 不是有效 URL 时（如 EdgeOne 的占位值 "relative"），跳过 rewrites
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    if (!apiUrl.startsWith('http')) return [];
    return [
      {
        source: '/api/v1/:path*',
        destination: `${apiUrl}/api/v1/:path*`,
      },
    ];
  },
}

module.exports = nextConfig
