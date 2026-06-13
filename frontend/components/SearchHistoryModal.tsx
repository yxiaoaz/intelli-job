'use client';

import { useState, useEffect } from 'react';
import { X, Clock, Trash2, Search } from 'lucide-react';
import { useRouter } from 'next/navigation';

interface SearchHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface SearchRecord {
  keyword: string;
  mode: string;
  topK: string;
  timestamp: string;
}

export default function SearchHistoryModal({ isOpen, onClose }: SearchHistoryModalProps) {
  const router = useRouter();
  const [userId, setUserId] = useState<string>('');
  const [history, setHistory] = useState<SearchRecord[]>([]);
  const [loading, setLoading] = useState(true);

  // 获取用户 ID
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        setUserId(payload.sub || '');
      } catch (error) {
        console.error('Failed to decode token:', error);
      }
    }
  }, []);

  useEffect(() => {
    if (isOpen && userId) {
      loadHistory();
    }
  }, [isOpen, userId]);

  const loadHistory = () => {
    try {
      setLoading(true);
      // 从 localStorage 读取搜索历史（按用户隔离）
      const keyword = localStorage.getItem(`dashboard_search_${userId}_keyword`) || '';
      const mode = localStorage.getItem(`dashboard_search_${userId}_mode`) || 'hybrid';
      const topK = localStorage.getItem(`dashboard_search_${userId}_topK`) || '100';

      // 构建历史记录（简化版）
      const records: SearchRecord[] = [];
      
      // 如果有当前搜索
      if (keyword) {
        records.push({
          keyword,
          mode,
          topK,
          timestamp: new Date().toISOString(),
        });
      }

      // 尝试读取更多历史（如果需要）
      const savedHistory = JSON.parse(localStorage.getItem(`search_history_${userId}`) || '[]');
      records.push(...savedHistory);

      setHistory(records);
    } catch (error) {
      console.error('加载搜索历史失败:', error);
      setHistory([]);
    } finally {
      setLoading(false);
    }
  };

  const handleClearHistory = () => {
    if (!confirm('确定要清除所有搜索历史吗？')) return;

    try {
      localStorage.removeItem(`search_history_${userId}`);
      localStorage.removeItem(`dashboard_search_${userId}_keyword`);
      localStorage.removeItem(`dashboard_search_${userId}_mode`);
      localStorage.removeItem(`dashboard_search_${userId}_topK`);
      setHistory([]);
    } catch (error) {
      console.error('清除历史失败:', error);
    }
  };

  const handleSearchAgain = (record: SearchRecord) => {
    // 保存搜索参数（按用户隔离）
    localStorage.setItem(`dashboard_search_${userId}_keyword`, record.keyword);
    localStorage.setItem(`dashboard_search_${userId}_mode`, record.mode);
    localStorage.setItem(`dashboard_search_${userId}_topK`, record.topK);
    
    // 跳转到 Dashboard
    router.push('/dashboard');
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in">
      <div className="bg-white dark:bg-dark-800 rounded-2xl shadow-2xl max-w-3xl w-full max-h-[80vh] overflow-hidden flex flex-col animate-scale-in">
        
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-dark-600">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white font-display">
            搜索历史
          </h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-600 transition-colors"
          >
            <X className="w-5 h-5 text-gray-600 dark:text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-gray-500 dark:text-gray-400">加载中...</div>
            </div>
          ) : history.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Clock className="w-16 h-16 text-gray-300 dark:text-gray-600 mb-4" />
              <p className="text-gray-500 dark:text-gray-400">暂无搜索历史</p>
            </div>
          ) : (
            <div className="space-y-3">
              {history.map((record, index) => (
                <div
                  key={index}
                  className="glass rounded-xl p-4 border border-primary-200/50 dark:border-primary-700/50 card-hover"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <Search className="w-4 h-4 text-primary-600 dark:text-primary-400" />
                        <h3 className="font-semibold text-gray-900 dark:text-white">
                          {record.keyword}
                        </h3>
                      </div>
                      <div className="flex gap-4 text-sm text-gray-600 dark:text-gray-400">
                        <span>模式: {record.mode}</span>
                        <span>Top K: {record.topK}</span>
                        <span>{new Date(record.timestamp).toLocaleString('zh-CN')}</span>
                      </div>
                    </div>
                    
                    <button
                      onClick={() => handleSearchAgain(record)}
                      className="p-2 rounded-lg hover:bg-primary-50 dark:hover:bg-dark-600 transition-colors"
                      title="重新搜索"
                    >
                      <Search className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 dark:border-dark-600 flex gap-3">
          <button
            onClick={handleClearHistory}
            disabled={history.length === 0}
            className="flex items-center gap-2 px-6 py-3 bg-red-100 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-xl hover:bg-red-200 dark:hover:bg-red-900/30 transition-all font-medium disabled:opacity-50"
          >
            <Trash2 className="w-4 h-4" />
            清除历史
          </button>
          <button
            onClick={onClose}
            className="flex-1 px-6 py-3 bg-gradient-to-r from-primary-600 to-primary-500 text-white rounded-xl hover:from-primary-700 hover:to-primary-600 transition-all font-medium"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}
