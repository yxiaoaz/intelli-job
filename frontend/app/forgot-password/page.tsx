'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { authAPI } from '@/lib/api';

type Step = 'username' | 'question' | 'reset';

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>('username');
  const [username, setUsername] = useState('');
  const [securityQuestion, setSecurityQuestion] = useState('');
  const [securityAnswer, setSecurityAnswer] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Step 1: Request security question
  const handleRequestQuestion = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await authAPI.forgotPassword(username);
      setSecurityQuestion(response.data.security_question);
      setStep('question');
    } catch (err: any) {
      setError(err.response?.data?.detail || '请求失败，请检查用户名是否正确');
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Verify answer and reset password
  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (newPassword !== confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }

    if (newPassword.length < 8) {
      setError('密码长度至少为8个字符');
      return;
    }

    setLoading(true);

    try {
      await authAPI.resetPassword(username, securityAnswer, newPassword);
      // Redirect to login after successful reset
      router.push('/login?reset=success');
    } catch (err: any) {
      setError(err.response?.data?.detail || '重置失败，请检查答案是否正确');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-dark-50 via-white to-primary-50
                 dark:from-dark-900 dark:via-dark-800 dark:to-dark-900 py-12 px-4 sm:px-6 lg:px-8 animate-fade-in">
      <div className="max-w-md w-full space-y-10">
        {/* Logo and Title */}
        <div className="text-center">
          <div className="mx-auto h-20 w-20 bg-gradient-to-br from-primary-500 via-accent-cyan to-primary-600 rounded-3xl flex items-center justify-center shadow-glow-lg mb-8 transform hover:scale-110 transition-all duration-300">
            <svg className="h-11 w-11 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
          </div>
          <h2 className="text-5xl font-bold gradient-text mb-3 font-display">
            找回密码
          </h2>
          <p className="text-base text-gray-700 dark:text-gray-300">
            {step === 'username' && '输入你的用户名'}
            {step === 'question' && '回答安全问题以验证身份'}
            {step === 'reset' && '设置新密码'}
          </p>
        </div>

        {/* Form Card */}
        <div className="glass rounded-3xl shadow-xl p-8 space-y-6 border border-primary-200/50 dark:border-primary-700/50 card-hover">
          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border-l-4 border-red-500 text-red-700 dark:text-red-300 px-4 py-3 rounded-lg text-sm animate-fade-in">
              {error}
            </div>
          )}

          {/* Step 1: Username Input */}
          {step === 'username' && (
            <form onSubmit={handleRequestQuestion} className="space-y-5">
              <div>
                <label htmlFor="username" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  用户名
                </label>
                <input
                  id="username"
                  name="username"
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full px-4 py-3 border-2 border-gray-300 dark:border-dark-500 rounded-xl
                             placeholder-gray-400 dark:placeholder-gray-500 text-gray-900 dark:text-white
                             bg-white dark:bg-dark-600
                             focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
                             transition-all duration-200 hover:border-primary-400 dark:hover:border-primary-600"
                  placeholder="请输入注册用户名"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 px-4 bg-gradient-to-r from-primary-600 via-primary-500 to-accent-cyan hover:from-primary-700 hover:via-primary-600 hover:to-accent-teal
                           text-white font-bold rounded-xl shadow-lg hover:shadow-glow
                           focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 dark:focus:ring-offset-dark-800
                           disabled:opacity-50 disabled:cursor-not-allowed
                           transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98]"
              >
                {loading ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    查询中...
                  </span>
                ) : (
                  '下一步'
                )}
              </button>
            </form>
          )}

          {/* Step 2: Security Question Answer */}
          {step === 'question' && (
            <form onSubmit={handleResetPassword} className="space-y-5">
              <div className="bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-500 p-4 rounded-lg">
                <p className="text-sm text-blue-700 dark:text-blue-300 font-medium mb-2">安全问题：</p>
                <p className="text-base text-gray-900 dark:text-white">{securityQuestion}</p>
              </div>

              <div>
                <label htmlFor="securityAnswer" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  你的答案
                </label>
                <input
                  id="securityAnswer"
                  name="answer_field" // 使用不同的 name 避免浏览器自动填充
                  type="text"
                  required
                  value={securityAnswer}
                  onChange={(e) => setSecurityAnswer(e.target.value)}
                  autoComplete="off" // 禁用自动填充
                  className="w-full px-4 py-3 border-2 border-gray-300 dark:border-dark-500 rounded-xl
                             placeholder-gray-400 dark:placeholder-gray-500 text-gray-900 dark:text-white
                             bg-white dark:bg-dark-600
                             focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
                             transition-all duration-200 hover:border-primary-400 dark:hover:border-primary-600"
                  placeholder="请输入答案"
                />
              </div>

              <div>
                <label htmlFor="newPassword" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  新密码
                </label>
                <input
                  id="newPassword"
                  name="newPassword"
                  type="password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full px-4 py-3 border-2 border-gray-300 dark:border-dark-500 rounded-xl
                             placeholder-gray-400 dark:placeholder-gray-500 text-gray-900 dark:text-white
                             bg-white dark:bg-dark-600
                             focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
                             transition-all duration-200 hover:border-primary-400 dark:hover:border-primary-600"
                  placeholder="至少8个字符"
                />
              </div>

              <div>
                <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  确认新密码
                </label>
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-4 py-3 border-2 border-gray-300 dark:border-dark-500 rounded-xl
                             placeholder-gray-400 dark:placeholder-gray-500 text-gray-900 dark:text-white
                             bg-white dark:bg-dark-600
                             focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
                             transition-all duration-200 hover:border-primary-400 dark:hover:border-primary-600"
                  placeholder="再次输入新密码"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 px-4 bg-gradient-to-r from-primary-600 via-primary-500 to-accent-cyan hover:from-primary-700 hover:via-primary-600 hover:to-accent-teal
                           text-white font-bold rounded-xl shadow-lg hover:shadow-glow
                           focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 dark:focus:ring-offset-dark-800
                           disabled:opacity-50 disabled:cursor-not-allowed
                           transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98]"
              >
                {loading ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    重置中...
                  </span>
                ) : (
                  '重置密码'
                )}
              </button>

              <button
                type="button"
                onClick={() => setStep('username')}
                className="w-full py-2 px-4 text-sm text-gray-600 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400
                           transition-colors duration-200"
              >
                ← 返回上一步
              </button>
            </form>
          )}
        </div>

        {/* Footer Links */}
        <div className="text-center">
          <p className="text-sm text-gray-700 dark:text-gray-300">
            想起密码了？{' '}
            <Link
              href="/login"
              className="font-semibold text-primary-600 hover:text-primary-500 dark:text-primary-400 dark:hover:text-primary-300
                         transition-colors duration-200"
            >
              返回登录
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
