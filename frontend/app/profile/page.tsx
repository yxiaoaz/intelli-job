'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { User, Calendar, LogOut, Settings, Bookmark, Clock, Lock } from 'lucide-react';
import { jobAPI, chatAPI, userAPI } from '@/lib/api';
import Navbar from '@/components/Navbar';
import FavoritesModal from '@/components/FavoritesModal';
import SearchHistoryModal from '@/components/SearchHistoryModal';
import PasswordChangeModal from '@/components/PasswordChangeModal';


export default function ProfilePage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [userCreatedAt, setUserCreatedAt] = useState('');
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ searches: 0, bookmarks: 0, chats: 0 });
  const [showFavorites, setShowFavorites] = useState(false);
  const [showSearchHistory, setShowSearchHistory] = useState(false);
  const [showPasswordChange, setShowPasswordChange] = useState(false);

  // Check authentication on mount
  useEffect(() => {
    const loadUserProfile = async () => {
      const token = localStorage.getItem('access_token');
      if (!token) {
        router.push('/login');
        return;
      }

      try {
        // Try to get user info from token (decoded)
        const payload = JSON.parse(atob(token.split('.')[1]));
        setUsername(payload.sub || '未知用户');
        
        // Get full user profile from API for created_at
        try {
          const response = await userAPI.getProfile();
          if (response.data && response.data.created_at) {
            const date = new Date(response.data.created_at);
            setUserCreatedAt(date.toISOString().split('T')[0]); // Format: YYYY-MM-DD
          } else {
            setUserCreatedAt('未知');
          }
        } catch (error) {
          console.error('获取用户信息失败:', error);
          setUserCreatedAt('未知');
        }
      } catch (error) {
        console.error('Failed to decode token:', error);
        setUsername('未知用户');
        setUserCreatedAt('未知');
      } finally {
        setLoading(false);
      }
    };

    loadUserProfile();
  }, [router]);

  // Load statistics
  useEffect(() => {
    const loadStats = async () => {
      try {
        // 获取搜索历史次数（从 localStorage）
        const searchHistory = JSON.parse(localStorage.getItem('search_history') || '[]');
        const searchCount = searchHistory.length;

        // 获取收藏职位数
        let bookmarkCount = 0;
        try {
          const bookmarksResponse = await jobAPI.bookmarks.getList();
          bookmarkCount = bookmarksResponse.data?.length || 0;
        } catch (error) {
          console.error('获取收藏列表失败:', error);
        }

        // 获取对话次数
        let chatCount = 0;
        try {
          const sessionsResponse = await chatAPI.getSessions();
          chatCount = sessionsResponse.data?.length || 0;
        } catch (error) {
          console.error('获取会话列表失败:', error);
        }

        setStats({
          searches: searchCount,
          bookmarks: bookmarkCount,
          chats: chatCount,
        });
      } catch (error) {
        console.error('加载统计数据失败:', error);
      }
    };

    loadStats();
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    router.push('/login');
  };

  return (
    <div className="min-h-screen bg-base animate-fade-in">
      {/* Header */}
      <Navbar currentPath="/profile" />

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 py-8">
        <div className="grid gap-6">
          {/* Profile Card */}
          <div className="bg-layer1 border border-l1 rounded-menu shadow-lv1 p-6">
            <div className="flex items-center gap-4 mb-6">
              <div className="w-20 h-20 bg-primary-500 rounded-full flex items-center justify-center">
                <User className="w-10 h-10 text-white" />
              </div>
              <div>
                <h2 className="text-2xl font-medium text-900">
                  {loading ? '加载中...' : username}
                </h2>
                <p className="text-700">求职者</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-3 text-700">
                <User className="w-5 h-5 text-primary-500" />
                <span>{username}</span>
              </div>
              <div className="flex items-center gap-3 text-700">
                <Calendar className="w-5 h-5 text-primary-500" />
                <span>注册时间: {loading ? '加载中...' : userCreatedAt}</span>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-layer1 border border-l1 rounded-menu shadow-lv1 p-6">
            <h3 className="text-lg font-medium mb-4 text-900 flex items-center gap-2">
              <Settings className="w-5 h-5 text-primary-500" />
              快捷操作
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <button
                onClick={() => router.push('/dashboard')}
                className="p-4 border border-l2 rounded-menu hover:bg-hover-primary transition-colors duration-base ease-ds text-left"
              >
                <div className="font-medium text-900 mb-1">搜索职位</div>
                <div className="text-sm text-700">查找心仪的工作机会</div>
              </button>

              <button
                onClick={() => router.push('/chat')}
                className="p-4 border border-l2 rounded-menu hover:bg-hover-primary transition-colors duration-base ease-ds text-left"
              >
                <div className="font-medium text-900 mb-1">AI助手</div>
                <div className="text-sm text-700">获取求职建议</div>
              </button>

              <button
                onClick={() => setShowFavorites(true)}
                className="p-4 border border-l2 rounded-menu hover:bg-hover-neutral transition-colors duration-base ease-ds text-left"
              >
                <div className="flex items-center mb-1">
                  <Bookmark className="w-4 h-4 text-primary-500 mr-2" />
                  <div className="font-medium text-900">我的收藏</div>
                </div>
                <div className="text-sm text-700">查看收藏的职位</div>
              </button>

              <button
                onClick={() => setShowSearchHistory(true)}
                className="p-4 border border-l2 rounded-menu hover:bg-hover-neutral transition-colors duration-base ease-ds text-left"
              >
                <div className="flex items-center mb-1">
                  <Clock className="w-4 h-4 text-success-600 mr-2" />
                  <div className="font-medium text-900">搜索历史</div>
                </div>
                <div className="text-sm text-700">查看搜索记录</div>
              </button>
            </div>
          </div>

          {/* Account Settings */}
          <div className="bg-layer1 border border-l1 rounded-menu shadow-lv1 p-6">
            <h3 className="text-lg font-medium mb-4 text-900">账号设置</h3>
            
            <div className="space-y-3">
              <button
                onClick={() => setShowPasswordChange(true)}
                className="w-full p-4 border border-l2 rounded-menu hover:bg-hover-primary transition-colors duration-base ease-ds text-left flex justify-between items-center"
              >
                <div className="flex items-center gap-3">
                  <Lock className="w-5 h-5 text-primary-500" />
                  <div>
                    <div className="font-medium text-900">修改密码</div>
                    <div className="text-sm text-700">更新您的登录密码</div>
                  </div>
                </div>
                <span className="text-400">→</span>
              </button>

              <button
                onClick={handleLogout}
                className="w-full p-4 border border-danger-100 rounded-menu hover:bg-danger-100 transition-colors duration-base ease-ds text-left flex justify-between items-center"
              >
                <div>
                  <div className="font-medium text-danger-600">退出登录</div>
                  <div className="text-sm text-700">安全退出当前账号</div>
                </div>
                <LogOut className="w-5 h-5 text-danger-600" />
              </button>
            </div>
          </div>

          {/* Stats */}
          <div className="bg-primary-500 rounded-menu shadow-lv1 p-6 text-white">
            <h3 className="text-lg font-medium mb-4">数据统计</h3>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-3xl font-medium">{stats.searches}</div>
                <div className="text-sm opacity-90">搜索次数</div>
              </div>
              <div>
                <div className="text-3xl font-medium">{stats.bookmarks}</div>
                <div className="text-sm opacity-90">收藏职位</div>
              </div>
              <div>
                <div className="text-3xl font-medium">{stats.chats}</div>
                <div className="text-sm opacity-90">对话次数</div>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Modals */}
      <FavoritesModal isOpen={showFavorites} onClose={() => setShowFavorites(false)} />
      <SearchHistoryModal isOpen={showSearchHistory} onClose={() => setShowSearchHistory(false)} />
      <PasswordChangeModal isOpen={showPasswordChange} onClose={() => setShowPasswordChange(false)} />
    </div>
  );
}
