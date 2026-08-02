import { NextRequest, NextResponse } from 'next/server';

/**
 * API 反向代理 Route Handler
 * 
 * 将前端 /api/v1/* 请求代理到后端服务器，解决 EdgeOne Makers 不支持 edgeone.json 外部 URL 代理的问题。
 * 
 * 工作原理：
 *   客户端 → /api/v1/auth/login (同域) → Route Handler → BACKEND_URL/api/v1/auth/login
 * 
 * 环境变量：
 *   API_BACKEND_URL - 后端服务器地址（服务端专用，不暴露给客户端）
 *   默认值: http://localhost:8000（本地开发）
 * 
 * 支持特性：
 *   - 所有 HTTP 方法 (GET/POST/PUT/DELETE/PATCH)
 *   - SSE 流式响应透传（通过 ReadableStream）
 *   - 请求头转发（Authorization、Content-Type 等）
 *   - 请求体转发（POST/PUT/PATCH）
 */

const BACKEND_URL = process.env.API_BACKEND_URL || 'http://localhost:8000';

// Hop-by-hop headers 不应被转发
const HOP_BY_HOP_HEADERS = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
  'host',
  'content-length',
]);

async function proxyRequest(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const apiPath = path.join('/');
  const searchParams = request.nextUrl.search;
  const backendUrl = `${BACKEND_URL}/api/v1/${apiPath}${searchParams}`;

  // 构建转发请求头
  const forwardHeaders = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      forwardHeaders.set(key, value);
    }
  });

  // 构建 fetch 选项
  const fetchOptions: RequestInit = {
    method: request.method,
    headers: forwardHeaders,
  };

  // GET 和 HEAD 不能有 body
  if (!['GET', 'HEAD'].includes(request.method)) {
    fetchOptions.body = await request.arrayBuffer();
  }

  try {
    const backendResponse = await fetch(backendUrl, fetchOptions);

    // 构建响应头，过滤 hop-by-hop headers
    const responseHeaders = new Headers();
    backendResponse.headers.forEach((value, key) => {
      if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
        responseHeaders.set(key, value);
      }
    });

    // 返回响应，透传 body stream（支持 SSE）
    return new NextResponse(backendResponse.body, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error(`[API Proxy] ${request.method} ${backendUrl} failed:`, error);
    return NextResponse.json(
      { error: 'API proxy error', message: error instanceof Error ? error.message : 'Unknown error' },
      { status: 502 }
    );
  }
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const DELETE = proxyRequest;
export const PATCH = proxyRequest;
