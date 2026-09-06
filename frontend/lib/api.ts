/**
 * API Client for Intelli-Job Backend
 */
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { toast } from 'sonner';

// 所有环境都走相对路径，由 Next.js Route Handler (app/api/v1/[...path]/route.ts) 代理到后端
// Route Handler 通过服务端环境变量 API_BACKEND_URL 获取后端地址
// 本地开发: .env.local 中设置 API_BACKEND_URL=http://localhost:8000
// EdgeOne: 控制台设置 API_BACKEND_URL=https://api.intelli-job.xyz
const API_BASE_URL = '';

// Create axios instance
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - add auth token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: any) => {
    return Promise.reject(error);
  }
);

// Response interceptor - handle token refresh
// ✅ 共享刷新函数：并发 401 只发一次 refresh 请求（promise 去重）
let refreshInFlight: Promise<string | null> | null = null;

export async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;
  const refreshToken = localStorage.getItem('refresh_token');
  if (!refreshToken) return null;

  refreshInFlight = (async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!res.ok) return null;
      const { access_token, refresh_token: newRefresh } = await res.json();
      localStorage.setItem('access_token', access_token);
      if (newRefresh) localStorage.setItem('refresh_token', newRefresh);
      return access_token as string;
    } catch {
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

// ✅ 登出收尾：清状态 + 提示 + 跳登录（仅在 refresh 也失败时调用）
function forceLogout(): void {
  setAuthFailed();
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('chat_session_id');
  toast.error('登录已过期，请重新登录');
  setTimeout(() => {
    window.location.href = '/login';
  }, 0);
}

// ✅ 全局认证失败标志：防止 401 死循环（持久化到 sessionStorage）
// 使用 sessionStorage 而不是模块级变量，因为 window.location.href 会重置模块状态
const AUTH_FAILED_KEY = 'auth_failed_redirecting';

function isAuthFailed(): boolean {
  return sessionStorage.getItem(AUTH_FAILED_KEY) === 'true';
}

function setAuthFailed(): void {
  sessionStorage.setItem(AUTH_FAILED_KEY, 'true');
}

function clearAuthFailed(): void {
  sessionStorage.removeItem(AUTH_FAILED_KEY);
}

// ✅ 导出清除函数，供登录成功后调用
export const resetGlobalAuthFailed = () => {
  clearAuthFailed();
};

apiClient.interceptors.response.use(
  (response: any) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // ✅ 已认证失败：立即拒绝所有请求
    if (isAuthFailed()) {
      console.warn('[API] Auth failed (sessionStorage), blocking request');
      return Promise.reject(error);
    }

    // ✅ 401 → 先尝试 refresh → 成功则重放原请求；失败才登出
    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true;
      console.log('[API] 401 detected, attempting token refresh...');

      const newToken = await refreshAccessToken();
      if (newToken) {
        console.log('[API] Token refreshed, replaying original request');
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      }

      console.log('[API] Refresh failed, redirecting to /login');
      forceLogout();
      return Promise.reject(new Error('Authentication required'));
    }

    return Promise.reject(error);
  }
);

// Auth APIs
export const authAPI = {
  register: (username: string, password: string, securityQuestion?: string, securityAnswer?: string) =>
    apiClient.post('/api/v1/auth/register', {
      username,
      password,
      security_question: securityQuestion || null,
      security_answer: securityAnswer || null,
    }),

  login: (username: string, password: string) =>
    apiClient.post('/api/v1/auth/login', { username, password }),

  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  },

  changePassword: (oldPassword: string, newPassword: string) =>
    apiClient.put('/api/v1/auth/password', {
      old_password: oldPassword,
      new_password: newPassword,
    }),

  // Forgot Password / Security Question
  forgotPassword: (username: string) =>
    apiClient.post('/api/v1/auth/forgot-password', { username }),

  resetPassword: (username: string, securityAnswer: string, newPassword: string) =>
    apiClient.post('/api/v1/auth/reset-password', {
      username,
      security_answer: securityAnswer,
      new_password: newPassword,
    }),

  getSecurityQuestionStatus: () =>
    apiClient.get('/api/v1/auth/security-question/status'),

  setSecurityQuestion: (question: string, answer: string) =>
    apiClient.post('/api/v1/auth/security-question', {
      security_question: question,
      security_answer: answer,
    }),
};

// Job APIs
export interface QueryEnhancement {
  expanded_query: string;
  synonyms: string[];
  category: string;
  original_keywords: string;
  resume_context?: { skills: string[]; latest_title?: string } | null;
}

export const jobAPI = {
  search: (params: {
    user_query_preference: { keywords?: string } | Record<string, never>;
    search_mode?: 'hybrid' | 'keyword' | 'vector';
    top_k?: number;
    hard_filters?: Record<string, any>;
  }) => apiClient.post('/api/v1/jobs/match', params),

  getDetail: (jobId: string) => apiClient.get(`/api/v1/jobs/${jobId}`),

  getAIExplanation: (jobId: string) => apiClient.post(`/api/v1/jobs/${jobId}/ai-explanation`),

  bookmarks: {
    getList: () => apiClient.get('/api/v1/jobs/bookmarks'),
    add: (jobId: string) => apiClient.post(`/api/v1/jobs/bookmarks/${jobId}`),
    remove: (jobId: string) => apiClient.delete(`/api/v1/jobs/bookmarks/${jobId}`),
    // section 级更新：传哪个改哪个；notes 传空串表示清空
    update: (
      jobId: string,
      payload: { status?: string; notes?: string }
    ) => apiClient.patch(`/api/v1/jobs/bookmarks/${jobId}`, payload),
  },
};

// Chat APIs
export const chatAPI = {
  createSession: () => apiClient.post('/api/v1/chat/sessions'),

  // Non-streaming (deprecated, kept for compatibility)
  sendMessage: (sessionId: string, message: string) =>
    apiClient.post(`/api/v1/chat/sessions/${sessionId}/messages`, {
      message,
    }),

  // Streaming (recommended)
  sendMessageStream: async (
    sessionId: string,
    message: string,
    onToken: (token: string) => void,
    onJobResults: (jobs: any[]) => void,
    onComplete: () => void,
    onError: (error: string) => void,
    signal?: AbortSignal,
    onToolStart?: (name: string, display: string) => void,
    onToolEnd?: (name: string) => void
  ) => {
    try {
      let response = await fetch(
        `${API_BASE_URL}/api/v1/chat/sessions/${sessionId}/messages/stream`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          },
          body: JSON.stringify({ message }),
          signal,
        }
      );

      if (!response.ok) {
        if (response.status === 401) {
          // ✅ 先尝试 refresh，成功则用新 token 重放一次
          const newToken = await refreshAccessToken();
          if (newToken) {
            response = await fetch(
              `${API_BASE_URL}/api/v1/chat/sessions/${sessionId}/messages/stream`,
              {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  'Authorization': `Bearer ${newToken}`,
                },
                body: JSON.stringify({ message }),
                signal,
              }
            );
          }
          if (!response.ok) {
            forceLogout();
            return;
          }
        } else {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';  // ✅ 处理 SSE 事件被 chunk 边界截断的情况

      if (!reader) {
        throw new Error('Response body is not readable');
      }

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          // 处理 buffer 中残余数据
          if (buffer.trim()) {
            const lines = buffer.split('\n');
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const event = JSON.parse(line.slice(6));
                  switch (event.type) {
                    case 'token': onToken(event.data); break;
                    case 'job_results': onJobResults(event.data?.jobs ?? []); break;
                    case 'final_response': onComplete(); break;
                    case 'error': onError(event.data); break;
                    case 'tool_start': onToolStart?.(event.data.name, event.data.display); break;
                    case 'tool_end': onToolEnd?.(event.data.name); break;
                  }
                } catch (e) {
                  console.error('Failed to parse SSE event:', e);
                }
              }
            }
          }
          break;
        }

        // ✅ stream: true 正确处理 UTF-8 多字节字符跨 chunk 边界
        buffer += decoder.decode(value, { stream: true });

        // 按双换行分割完整 SSE 事件
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';  // 最后一个不完整，留在 buffer

        for (const part of parts) {
          const lines = part.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const event = JSON.parse(line.slice(6));
                
                switch (event.type) {
                  case 'token':
                    onToken(event.data);
                    break;
                  case 'job_results':
                    onJobResults(event.data?.jobs ?? []);
                    break;
                  case 'final_response':
                    onComplete();
                    break;
                  case 'error':
                    onError(event.data);
                    break;
                  case 'tool_start':
                    onToolStart?.(event.data.name, event.data.display);
                    break;
                  case 'tool_end':
                    onToolEnd?.(event.data.name);
                    break;
                }
              } catch (e) {
                console.error('Failed to parse SSE event:', e);
              }
            }
          }
        }
      }
    } catch (error: any) {
      onError(error.message || 'Stream failed');
    }
  },

  getSessions: () => apiClient.get('/api/v1/chat/sessions'),

  getSession: (sessionId: string) =>
    apiClient.get(`/api/v1/chat/sessions/${sessionId}`),

  getMessages: (sessionId: string) =>
    apiClient.get(`/api/v1/chat/sessions/${sessionId}/messages`),

  deleteSession: (sessionId: string) =>
    apiClient.delete(`/api/v1/chat/sessions/${sessionId}`),
};

// Resume APIs
export interface ResumeSummary {
  latest_title: string | null;
  latest_company: string | null;
  highest_degree: string | null;
  skills_preview: string[];
  completeness: number | null;
  suggestion_count: number;
}

export const resumeAPI = {
  setDefault: (resumeId: string) =>
    apiClient.post(`/api/v1/resumes/${resumeId}/set-default`),

  updateProfile: (
    resumeId: string,
    payload: {
      personal_info?: Record<string, any>;
      skills?: string[];
      education?: Record<string, any>[];
      work_experience?: Record<string, any>[];
    }
  ) => apiClient.patch(`/api/v1/resumes/${resumeId}/profile`, payload),
};

// User APIs
export const userAPI = {
  getProfile: () => apiClient.get('/api/v1/auth/me'),

  getPreferences: () => apiClient.get('/api/v1/auth/preferences'),

  updatePreferences: (preferences: {
    intended_company?: string[];
    intended_company_type?: string[];
    intended_location?: string[];
    intended_industry?: string[];
    intended_position?: string[];
    job_type?: string[];
  }) => apiClient.put('/api/v1/auth/preferences', preferences),
};

/**
 * fetch 封装：自动附加 Authorization header，处理 401 跳转登录
 * 用于替代原生 fetch()，适用于不方便使用 axios 的场景（如 FormData 上传）
 */
export async function fetchWithAuth(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const response = await fetchWithAuthOnce(url, options);

  if (response.status === 401) {
    // 尝试刷新 token，成功则用新 token 重放一次
    const newToken = await refreshAccessToken();
    if (newToken) {
      const headers = new Headers(options.headers || {});
      headers.set('Authorization', `Bearer ${newToken}`);
      return fetch(url, { ...options, headers });
    }

    forceLogout();
    throw new Error('登录已过期，请重新登录');
  }

  return response;
}

/** 内部：单次带 Authorization 的 fetch（不做 401 处理） */
async function fetchWithAuthOnce(url: string, options: RequestInit): Promise<Response> {
  const token = localStorage.getItem('access_token');
  if (!token) {
    window.location.href = '/login';
    throw new Error('未登录');
  }

  const headers = new Headers(options.headers || {});
  headers.set('Authorization', `Bearer ${token}`);
  return fetch(url, { ...options, headers });
}

export default apiClient;
