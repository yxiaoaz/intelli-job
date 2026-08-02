/**
 * API Client for Intelli-Job Backend
 */
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

// EdgeOne Makers 不允许环境变量为空，需填入占位值（如 "relative"），代码会自动识别并当作空字符串
// 本地开发: .env.local 中设置 NEXT_PUBLIC_API_URL=http://localhost:8000
// Vercel: 在 dashboard 中设置 NEXT_PUBLIC_API_URL 为后端地址
const envApiUrl = process.env.NEXT_PUBLIC_API_URL || '';
const API_BASE_URL = envApiUrl.startsWith('http') ? envApiUrl : '';

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
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: any) => void;
  reject: (reason?: any) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// ✅ 防止重复刷新：记录上次刷新时间
let lastRefreshTime = 0;
const REFRESH_COOLDOWN = 3000; // 3秒冷却时间

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

    // ✅ 最高优先级：如果已认证失败，立即拒绝所有请求
    if (isAuthFailed()) {
      console.warn('[API] Auth failed (sessionStorage), blocking request');
      return Promise.reject(error);
    }

    // If 401 and not already retrying
    if (error.response?.status === 401 && !originalRequest?._retry) {
      // ✅ 立即设置持久化标志，阻止后续并发请求
      setAuthFailed();
      
      console.log('[API] 401 detected, initiating redirect...');
      
      // ✅ 清除所有认证信息
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('chat_session_id');
      
      // ✅ 使用 setTimeout 延迟跳转，让当前调用栈清空
      setTimeout(() => {
        console.log('[API] Executing redirect to /login');
        window.location.href = '/login';
      }, 0);
      
      // ✅ 立即返回被拒绝的 Promise
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
export const jobAPI = {
  search: (params: {
    user_query_preference: { keywords: string };
    search_mode?: 'hybrid' | 'keyword' | 'vector';
    top_k?: number;
    hard_filters?: Record<string, any>;
  }) => apiClient.post('/api/v1/jobs/match', params),

  getDetail: (jobId: string) => apiClient.get(`/api/v1/jobs/${jobId}`),

  bookmarks: {
    getList: () => apiClient.get('/api/v1/jobs/bookmarks'),
    add: (jobId: string) => apiClient.post(`/api/v1/jobs/bookmarks/${jobId}`),
    remove: (jobId: string) => apiClient.delete(`/api/v1/jobs/bookmarks/${jobId}`),
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
    signal?: AbortSignal
  ) => {
    try {
      const response = await fetch(
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
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
          return;
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('Response body is not readable');
      }

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

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
              }
            } catch (e) {
              console.error('Failed to parse SSE event:', e);
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
  const token = localStorage.getItem('access_token');
  if (!token) {
    window.location.href = '/login';
    throw new Error('未登录');
  }

  const headers = new Headers(options.headers || {});
  headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(url, { ...options, headers });

  if (response.status === 401) {
    // 尝试刷新 token
    const refreshToken = localStorage.getItem('refresh_token');
    if (refreshToken) {
      try {
        const refreshRes = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });

        if (refreshRes.ok) {
          const { access_token, refresh_token: newRefresh } = await refreshRes.json();
          localStorage.setItem('access_token', access_token);
          localStorage.setItem('refresh_token', newRefresh);

          // 用新 token 重试原请求
          headers.set('Authorization', `Bearer ${access_token}`);
          const retryResponse = await fetch(url, { ...options, headers });
          return retryResponse;
        }
      } catch {
        // 刷新失败，继续跳转
      }
    }

    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    window.location.href = '/login';
    throw new Error('登录已过期，请重新登录');
  }

  return response;
}

export default apiClient;
