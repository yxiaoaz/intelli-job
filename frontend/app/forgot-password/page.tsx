'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { authAPI } from '@/lib/api';
import { buttonClasses } from '@/components/ui/Button';

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
    <div className="min-h-screen flex items-center justify-center bg-base py-12 px-4 sm:px-6 lg:px-8 animate-fade-in">
      <div className="max-w-md w-full space-y-10">
        {/* Logo and Title */}
        <div className="text-center">
          <div className="mx-auto h-20 w-20 bg-primary-500 rounded-dialog flex items-center justify-center mb-8">
            <svg className="h-11 w-11 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
          </div>
          <h2 className="text-2xl font-medium text-900 mb-3">
            找回密码
          </h2>
          <p className="text-base text-700">
            {step === 'username' && '输入你的用户名'}
            {step === 'question' && '回答安全问题以验证身份'}
            {step === 'reset' && '设置新密码'}
          </p>
        </div>

        {/* Form Card */}
        <div className="bg-layer1 border border-l1 rounded-dialog shadow-lv1 p-8 space-y-6">
          {error && (
            <div className="bg-tint-danger border-l-4 border-danger-600 text-tint-danger px-4 py-3 rounded-menu text-sm animate-fade-in">
              {error}
            </div>
          )}

          {/* Step 1: Username Input */}
          {step === 'username' && (
            <form onSubmit={handleRequestQuestion} className="space-y-5">
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
                  placeholder="请输入注册用户名"
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
              <div className="bg-tint-primary border-l-4 border-primary-500 p-4 rounded-menu">
                <p className="text-sm text-tint-primary font-medium mb-2">安全问题：</p>
                <p className="text-base text-900">{securityQuestion}</p>
              </div>

              <div>
                <label htmlFor="securityAnswer" className="block text-sm font-medium text-700 mb-2">
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
                  className="input-field"
                  placeholder="请输入答案"
                />
              </div>

              <div>
                <label htmlFor="newPassword" className="block text-sm font-medium text-700 mb-2">
                  新密码
                </label>
                <input
                  id="newPassword"
                  name="newPassword"
                  type="password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="input-field"
                  placeholder="至少8个字符"
                />
              </div>

              <div>
                <label htmlFor="confirmPassword" className="block text-sm font-medium text-700 mb-2">
                  确认新密码
                </label>
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="input-field"
                  placeholder="再次输入新密码"
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
                    重置中...
                  </span>
                ) : (
                  '重置密码'
                )}
              </button>

              <button
                type="button"
                onClick={() => setStep('username')}
                className="w-full py-2 px-4 text-sm text-700 hover:text-tint-primary
                           transition-colors duration-base"
              >
                ← 返回上一步
              </button>
            </form>
          )}
        </div>

        {/* Footer Links */}
        <div className="text-center">
          <p className="text-sm text-700">
            想起密码了？{' '}
            <Link
              href="/login"
              className="font-medium text-primary-600 hover:text-tint-primary
                         transition-colors duration-base"
            >
              返回登录
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
