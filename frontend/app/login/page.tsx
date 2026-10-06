'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { authAPI } from '@/lib/api';
import { buttonClasses } from '@/components/ui/Button';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await authAPI.login(username, password);
      const { access_token, refresh_token } = response.data;

      // Save tokens
      localStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);

      // ✅ 清除认证失败标志（登录成功后）
      sessionStorage.removeItem('auth_failed_redirecting');

      // Redirect to dashboard
      router.push('/dashboard');
    } catch (err: any) {
      setError(
        err.response?.data?.detail || '登录失败，请检查用户名和密码'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-base py-12 px-4 sm:px-6 lg:px-8 animate-fade-in">
      <div className="max-w-md w-full space-y-10">
        {/* Logo and Title */}
        <div className="text-center">
          <div className="mx-auto h-20 w-20 bg-primary-500 rounded-dialog flex items-center justify-center mb-8">
            <svg className="h-11 w-11 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <h2 className="text-2xl font-medium text-900 mb-3">
            欢迎回来
          </h2>
          <p className="text-base text-700">
            登录你的 Intelli-Job 账号
          </p>
        </div>

        {/* Login Form Card - 玻璃态 */}
        <div className="bg-layer1 border border-l1 rounded-dialog shadow-lv1 p-8 space-y-6">
          {error && (
            <div className="bg-tint-danger border-l-4 border-danger-600 text-tint-danger px-4 py-3 rounded-menu text-sm animate-fade-in">
              {error}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-700 mb-2">
                用户名
              </label>
              <input
                id="username"
                name="username"
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input-field"
                placeholder="请输入用户名"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-700 mb-2">
                密码
              </label>
              <input
                id="password"
                name="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-field"
                placeholder="请输入密码"
              />
              <div className="mt-2 text-right">
                <Link
                  href="/forgot-password"
                  className="text-sm text-primary-600 hover:text-primary-500 transition-colors duration-base ease-ds"
                >
                  忘记密码？
                </Link>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className={buttonClasses('primary', 'md', 'w-full')}
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  登录中...
                </span>
              ) : (
                '登 录'
              )}
            </button>
          </form>
        </div>

        {/* Footer Links */}
        <div className="text-center">
          <p className="text-sm text-700">
            还没有账号？{' '}
            <Link
              href="/register"
              className="font-medium text-primary-600 hover:text-tint-primary
                         transition-colors duration-base"
            >
              立即注册
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
