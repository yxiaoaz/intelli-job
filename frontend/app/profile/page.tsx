'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { User, Mail, Calendar, LogOut, Settings } from 'lucide-react';

export default function ProfilePage() {
  const router = useRouter();
  const [userEmail, setUserEmail] = useState('');
  const [loading, setLoading] = useState(true);

  // Check authentication on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/login');
      return;
    }

    // Try to get user info from token (decoded)
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      setUserEmail(payload.sub || '未知用户');
    } catch (error) {
      console.error('Failed to decode token:', error);
      setUserEmail('未知用户');
    } finally {
      setLoading(false);
    }
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    router.push('/login');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-dark-50 via-white to-primary-50 dark:from-dark-900 dark:via-dark-800 dark:to-dark-900 animate-fade-in">
      {/* Header - 玻璃态 */}
      <header className="glass shadow-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold gradient-text font-display">Intelli-Job</h1>
          <nav className="space-x-6">
            <button
              onClick={() => router.push('/dashboard')}
              className="text-gray-700 dark:text-gray-300 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
            >
              职位搜索
            </button>
            <button
              onClick={() => router.push('/chat')}
              className="text-gray-700 dark:text-gray-300 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
            >
              AI助手
            </button>
            <button
              onClick={() => router.push('/profile')}
              className="text-primary-600 dark:text-primary-400 font-semibold"
            >
              我的资料
            </button>
            <button
              onClick={handleLogout}
              className="text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 flex items-center gap-1 transition-colors"
            >
              <LogOut className="w-4 h-4" />
              退出
            </button>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 py-8">
        <div className="grid gap-6">
          {/* Profile Card - 玻璃态 */}
          <div className="glass rounded-2xl shadow-lg p-6 border border-primary-200/50 dark:border-primary-700/50 card-hover">
            <div className="flex items-center gap-4 mb-6">
              <div className="w-20 h-20 bg-gradient-to-br from-primary-500 to-primary-600 rounded-full flex items-center justify-center shadow-lg">
                <User className="w-10 h-10 text-white" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white font-display">
                  {loading ? '加载中...' : userEmail}
                </h2>
                <p className="text-gray-700 dark:text-gray-300">求职者</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-3 text-gray-700 dark:text-gray-300">
                <Mail className="w-5 h-5 text-primary-500" />
                <span>{userEmail}</span>
              </div>
              <div className="flex items-center gap-3 text-gray-700 dark:text-gray-300">
                <Calendar className="w-5 h-5 text-primary-500" />
                <span>注册时间: 2026-05-30</span>
              </div>
            </div>
          </div>

          {/* Quick Actions - 玻璃态 */}
          <div className="glass rounded-2xl shadow-lg p-6 border border-primary-200/50 dark:border-primary-700/50 card-hover">
            <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white flex items-center gap-2 font-display">
              <Settings className="w-5 h-5 text-primary-500" />
              快捷操作
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <button
                onClick={() => router.push('/dashboard')}
                className="p-4 border-2 border-primary-200/50 dark:border-primary-700/50 rounded-xl hover:bg-primary-50/50 dark:hover:bg-dark-600/50 transition-all text-left card-hover"
              >
                <div className="font-medium text-gray-900 dark:text-white mb-1">搜索职位</div>
                <div className="text-sm text-gray-700 dark:text-gray-300">查找心仪的工作机会</div>
              </button>

              <button
                onClick={() => router.push('/chat')}
                className="p-4 border-2 border-primary-200/50 dark:border-primary-700/50 rounded-xl hover:bg-primary-50/50 dark:hover:bg-dark-600/50 transition-all text-left card-hover"
              >
                <div className="font-medium text-gray-900 dark:text-white mb-1">AI助手</div>
                <div className="text-sm text-gray-700 dark:text-gray-300">获取求职建议</div>
              </button>

              <button
                className="p-4 border-2 border-gray-200 dark:border-dark-600 rounded-xl hover:bg-gray-50/50 dark:hover:bg-dark-600/50 transition-all text-left opacity-50 cursor-not-allowed"
                title="功能开发中"
              >
                <div className="font-medium text-gray-900 dark:text-white mb-1">我的收藏</div>
                <div className="text-sm text-gray-700 dark:text-gray-300">查看收藏的职位</div>
              </button>

              <button
                className="p-4 border-2 border-gray-200 dark:border-dark-600 rounded-xl hover:bg-gray-50/50 dark:hover:bg-dark-600/50 transition-all text-left opacity-50 cursor-not-allowed"
                title="功能开发中"
              >
                <div className="font-medium text-gray-900 dark:text-white mb-1">搜索历史</div>
                <div className="text-sm text-gray-700 dark:text-gray-300">查看搜索记录</div>
              </button>
            </div>
          </div>

          {/* Account Settings - 玻璃态 */}
          <div className="glass rounded-2xl shadow-lg p-6 border border-primary-200/50 dark:border-primary-700/50 card-hover">
            <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white font-display">账号设置</h3>
            
            <div className="space-y-3">
              <button
                className="w-full p-4 border-2 border-primary-200/50 dark:border-primary-700/50 rounded-xl hover:bg-primary-50/50 dark:hover:bg-dark-600/50 transition-all text-left flex justify-between items-center opacity-50 cursor-not-allowed"
                title="功能开发中"
              >
                <div>
                  <div className="font-medium text-gray-900 dark:text-white">修改密码</div>
                  <div className="text-sm text-gray-700 dark:text-gray-300">更新您的登录密码</div>
                </div>
                <span className="text-gray-400">→</span>
              </button>

              <button
                className="w-full p-4 border-2 border-primary-200/50 dark:border-primary-700/50 rounded-xl hover:bg-primary-50/50 dark:hover:bg-dark-600/50 transition-all text-left flex justify-between items-center opacity-50 cursor-not-allowed"
                title="功能开发中"
              >
                <div>
                  <div className="font-medium text-gray-900 dark:text-white">求职偏好</div>
                  <div className="text-sm text-gray-700 dark:text-gray-300">设置期望城市、行业等</div>
                </div>
                <span className="text-gray-400">→</span>
              </button>

              <button
                onClick={handleLogout}
                className="w-full p-4 border-2 border-red-200 dark:border-red-800 rounded-xl hover:bg-red-50/50 dark:hover:bg-red-900/20 transition-all text-left flex justify-between items-center card-hover"
              >
                <div>
                  <div className="font-medium text-red-600 dark:text-red-400">退出登录</div>
                  <div className="text-sm text-gray-700 dark:text-gray-300">安全退出当前账号</div>
                </div>
                <LogOut className="w-5 h-5 text-red-600 dark:text-red-400" />
              </button>
            </div>
          </div>

          {/* Stats - 渐变卡片 */}
          <div className="bg-gradient-to-r from-primary-600 via-primary-500 to-accent-cyan rounded-2xl shadow-lg p-6 text-white card-hover">
            <h3 className="text-lg font-semibold mb-4 font-display">数据统计</h3>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-3xl font-bold">0</div>
                <div className="text-sm opacity-90">搜索次数</div>
              </div>
              <div>
                <div className="text-3xl font-bold">0</div>
                <div className="text-sm opacity-90">收藏职位</div>
              </div>
              <div>
                <div className="text-3xl font-bold">0</div>
                <div className="text-sm opacity-90">对话次数</div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
