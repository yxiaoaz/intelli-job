/** @type {import('next').NextConfig} */
const nextConfig = {
  // API 代理由 Route Handler (app/api/v1/[...path]/route.ts) 统一处理
  // EdgeOne Makers 不支持 next.config.js rewrites，详见 edgeone.json
}

module.exports = nextConfig
