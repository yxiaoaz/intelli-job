'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { authAPI } from '@/lib/api';
import { buttonClasses } from '@/components/ui/Button';

export default function RegisterPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [securityQuestion, setSecurityQuestion] = useState('');
  const [securityAnswer, setSecurityAnswer] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // 安全问题选项
  const securityQuestions = [
    '你的小学母校名称是什么？',
    '你最喜欢的电影是什么？',
    '你的宠物名字是什么？',
    '你出生的城市是哪里？',
    '你最喜欢的食物是什么？',
  ];

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }

    if (password.length < 8) {
      setError('密码长度至少为8个字符');
      return;
    }

    if (!securityQuestion) {
      setError('请选择一个安全问题');
      return;
    }

    if (!securityAnswer || securityAnswer.trim().length === 0) {
      setError('请填写安全问题答案');
      return;
    }

    setLoading(true);

    try {
      await authAPI.register(username, password, securityQuestion, securityAnswer.trim().toLowerCase());
      
      // Auto login after registration
      const loginResponse = await authAPI.login(username, password);
      const { access_token, refresh_token } = loginResponse.data;

      localStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);

      router.push('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || '注册失败，请稍后重试');
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
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
            </svg>
          </div>
          <h2 className="text-2xl font-medium text-900 mb-3">
            创建账号
          </h2>
          <p className="text-base text-700">
            开始你的智能求职之旅
          </p>
        </div>

        {/* Register Form Card - 玻璃态 */}
        <div className="bg-layer1 border border-l1 rounded-dialog shadow-lv1 p-8 space-y-6">
          {error && (
            <div className="bg-tint-danger border-l-4 border-danger-600 text-tint-danger px-4 py-3 rounded-menu text-sm animate-fade-in">
              {error}
            </div>
          )}

          <form onSubmit={handleRegister} className="space-y-5">
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
                placeholder="至少8个字符"
              />
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-700 mb-2">
                确认密码
              </label>
              <input
                id="confirmPassword"
                name="confirmPassword"
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="input-field"
                placeholder="再次输入密码"
              />
            </div>

            <div>
              <label htmlFor="securityQuestion" className="block text-sm font-medium text-700 mb-2">
                安全问题（用于找回密码）
              </label>
              <select
                id="securityQuestion"
                value={securityQuestion}
                onChange={(e) => setSecurityQuestion(e.target.value)}
                required
                className="input-field"
              >
                <option value="">选择一个安全问题</option>
                {securityQuestions.map((q, idx) => (
                  <option key={idx} value={q}>{q}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="securityAnswer" className="block text-sm font-medium text-700 mb-2">
                问题答案
              </label>
              <input
                id="securityAnswer"
                name="reg_answer_field" // 使用不同的 name 避免浏览器自动填充
                type="text"
                required
                value={securityAnswer}
                onChange={(e) => setSecurityAnswer(e.target.value)}
                autoComplete="off" // 禁用自动填充
                className="input-field"
                placeholder="请输入答案"
              />
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
                  注册中...
                </span>
              ) : (
                '注 册'
              )}
            </button>
          </form>
        </div>

        {/* Footer Links */}
        <div className="text-center">
          <p className="text-sm text-700">
            已有账号？{' '}
            <Link
              href="/login"
              className="font-medium text-primary-600 hover:text-tint-primary
                         transition-colors duration-base"
            >
              立即登录
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
