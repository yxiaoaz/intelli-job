'use client';

import { useState } from 'react';
import { X, Lock, Eye, EyeOff } from 'lucide-react';
import { authAPI } from '@/lib/api';
import Button from '@/components/ui/Button';

interface PasswordChangeModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function PasswordChangeModal({ isOpen, onClose }: PasswordChangeModalProps) {
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showOldPassword, setShowOldPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validation
    if (newPassword.length < 8) {
      setError('新密码至少需要 8 个字符');
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('两次输入的新密码不一致');
      return;
    }

    if (oldPassword === newPassword) {
      setError('新密码不能与旧密码相同');
      return;
    }

    try {
      setSubmitting(true);
      await authAPI.changePassword(oldPassword, newPassword);
      setSuccess(true);
      
      // 3秒后关闭
      setTimeout(() => {
        onClose();
        resetForm();
      }, 2000);
    } catch (err: any) {
      const message = err.response?.data?.detail || '密码修改失败，请检查旧密码是否正确';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  const resetForm = () => {
    setOldPassword('');
    setNewPassword('');
    setConfirmPassword('');
    setError('');
    setSuccess(false);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in">
      <div className="bg-layer1 rounded-dialog border border-l1 shadow-lv3 max-w-md w-full animate-fade-in">
        
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-l1">
          <h2 className="text-xl font-medium text-900">
            修改密码
          </h2>
          <button
            onClick={onClose}
            className="p-2 rounded-input hover:bg-hover-neutral transition-colors"
          >
            <X className="w-5 h-5 text-500" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {success ? (
            <div className="text-center py-8">
              <div className="text-success-600 text-lg font-medium mb-2">
                密码修改成功！
              </div>
              <div className="text-500 text-sm">
                请使用新密码登录
              </div>
            </div>
          ) : (
            <>
              {/* Old Password */}
              <div>
                <label className="block text-sm font-medium text-700 mb-2">
                  旧密码
                </label>
                <div className="relative">
                  <input
                    type={showOldPassword ? 'text' : 'password'}
                    value={oldPassword}
                    onChange={(e) => setOldPassword(e.target.value)}
                    required
                    className="w-full px-4 py-3 pr-11 rounded-input border border-l2 bg-base text-900 focus:outline-none focus:ring-2 focus:ring-primary-200 transition-colors"
                    placeholder="请输入旧密码"
                  />
                  <button
                    type="button"
                    onClick={() => setShowOldPassword(!showOldPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-input hover:bg-hover-neutral transition-colors"
                  >
                    {showOldPassword ? (
                      <EyeOff className="w-5 h-5 text-500" />
                    ) : (
                      <Eye className="w-5 h-5 text-500" />
                    )}
                  </button>
                </div>
              </div>

              {/* New Password */}
              <div>
                <label className="block text-sm font-medium text-700 mb-2">
                  新密码
                </label>
                <div className="relative">
                  <input
                    type={showNewPassword ? 'text' : 'password'}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    minLength={8}
                    className="w-full px-4 py-3 pr-11 rounded-input border border-l2 bg-base text-900 focus:outline-none focus:ring-2 focus:ring-primary-200 transition-colors"
                    placeholder="至少 8 个字符"
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPassword(!showNewPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-input hover:bg-hover-neutral transition-colors"
                  >
                    {showNewPassword ? (
                      <EyeOff className="w-5 h-5 text-500" />
                    ) : (
                      <Eye className="w-5 h-5 text-500" />
                    )}
                  </button>
                </div>
              </div>

              {/* Confirm Password */}
              <div>
                <label className="block text-sm font-medium text-700 mb-2">
                  确认新密码
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  className="w-full px-4 py-3 rounded-input border border-l2 bg-base text-900 focus:outline-none focus:ring-2 focus:ring-primary-200 transition-colors"
                  placeholder="再次输入新密码"
                />
              </div>

              {/* Error Message */}
              {error && (
                <div className="p-3 bg-tint-danger border border-danger-100 rounded-input text-sm text-danger-600">
                  {error}
                </div>
              )}

              {/* Submit Button */}
              <Button
                type="submit"
                variant="primary"
                disabled={submitting || !oldPassword || !newPassword || !confirmPassword}
                className="w-full px-6"
              >
                <Lock className="w-4 h-4" />
                {submitting ? '提交中...' : '确认修改'}
              </Button>
            </>
          )}
        </form>
      </div>
    </div>
  );
}
