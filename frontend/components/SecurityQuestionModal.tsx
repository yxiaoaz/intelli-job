'use client';

import { useState } from 'react';
import { authAPI } from '@/lib/api';
import { toast } from 'sonner';

interface SecurityQuestionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

const securityQuestions = [
  '你的小学母校名称是什么？',
  '你最喜欢的电影是什么？',
  '你的宠物名字是什么？',
  '你出生的城市是哪里？',
  '你最喜欢的食物是什么？',
];

export default function SecurityQuestionModal({ isOpen, onClose, onSuccess }: SecurityQuestionModalProps) {
  const [securityQuestion, setSecurityQuestion] = useState('');
  const [securityAnswer, setSecurityAnswer] = useState('');
  const [settingSecurityQuestion, setSettingSecurityQuestion] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!securityQuestion) {
      setError('请选择一个安全问题');
      return;
    }

    if (!securityAnswer || securityAnswer.trim().length === 0) {
      setError('请填写答案');
      return;
    }

    setSettingSecurityQuestion(true);
    try {
      await authAPI.setSecurityQuestion(securityQuestion, securityAnswer.trim().toLowerCase());
      toast.success('安全问题设置成功');
      onSuccess?.();
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || '设置失败，请稍后重试');
    } finally {
      setSettingSecurityQuestion(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in">
      <div className="glass rounded-3xl shadow-2xl p-8 max-w-md w-full border border-primary-200/50 dark:border-primary-700/50">
        <div className="text-center mb-6">
          <div className="mx-auto h-16 w-16 bg-gradient-to-br from-primary-500 via-accent-cyan to-primary-600 rounded-2xl flex items-center justify-center shadow-glow-lg mb-4">
            <svg className="h-9 w-9 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h3 className="text-2xl font-bold gradient-text mb-2">设置安全问题</h3>
          <p className="text-sm text-gray-700 dark:text-gray-300">
            为了保障你的账号安全，请设置一个安全问题用于找回密码
          </p>
        </div>

        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border-l-4 border-red-500 text-red-700 dark:text-red-300 px-4 py-3 rounded-lg text-sm mb-4 animate-fade-in">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="sq-modal" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              选择一个安全问题
            </label>
            <select
              id="sq-modal"
              value={securityQuestion}
              onChange={(e) => setSecurityQuestion(e.target.value)}
              required
              className="w-full px-4 py-3 border-2 border-gray-300 dark:border-dark-500 rounded-xl
                         text-gray-900 dark:text-white
                         bg-white dark:bg-dark-600
                         focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
                         transition-all duration-200 hover:border-primary-400 dark:hover:border-primary-600"
            >
              <option value="">选择一个安全问题</option>
              {securityQuestions.map((q, idx) => (
                <option key={idx} value={q}>{q}</option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="sa-modal" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              问题答案
            </label>
            <input
              id="sa-modal"
              name="security_answer_field"
              type="text"
              required
              value={securityAnswer}
              onChange={(e) => setSecurityAnswer(e.target.value)}
              autoComplete="off"
              className="w-full px-4 py-3 border-2 border-gray-300 dark:border-dark-500 rounded-xl
                         placeholder-gray-400 dark:placeholder-gray-500 text-gray-900 dark:text-white
                         bg-white dark:bg-dark-600
                         focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
                         transition-all duration-200 hover:border-primary-400 dark:hover:border-primary-600"
              placeholder="请输入答案"
            />
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-3 px-4 border-2 border-gray-300 dark:border-dark-500 text-gray-700 dark:text-gray-300
                         font-semibold rounded-xl hover:bg-gray-50 dark:hover:bg-dark-700
                         transition-all duration-200"
            >
              稍后设置
            </button>
            <button
              type="submit"
              disabled={settingSecurityQuestion}
              className="flex-1 py-3 px-4 bg-gradient-to-r from-primary-600 via-primary-500 to-accent-cyan hover:from-primary-700 hover:via-primary-600 hover:to-accent-teal
                         text-white font-bold rounded-xl shadow-lg hover:shadow-glow
                         disabled:opacity-50 disabled:cursor-not-allowed
                         transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98]"
            >
              {settingSecurityQuestion ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  设置中...
                </span>
              ) : (
                '确认设置'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
