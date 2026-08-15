'use client';

import { useState, useEffect } from 'react';
import { X, Clock, Trash2, Search } from 'lucide-react';
import { formatRelativeTime } from '@/lib/time';

interface SearchHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect?: (record: { keyword: string; topK: number }) => void;
}

interface SearchRecord {
  keyword: string;
  topK: number;
  timestamp: string;
}

export default function SearchHistoryModal({ isOpen, onClose, onSelect }: SearchHistoryModalProps) {
  const [userId, setUserId] = useState<string>('');
  const [history, setHistory] = useState<SearchRecord[]>([]);

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
      const historyKey = `search_history_${userId}`;
      const saved: SearchRecord[] = JSON.parse(localStorage.getItem(historyKey) || '[]');
      setHistory(saved);
    } catch (error) {
      console.error('加载搜索历史失败:', error);
      setHistory([]);
    }
  };

  const handleClearHistory = () => {
    if (!confirm('确定要清除所有搜索历史吗？')) return;
    try {
      localStorage.removeItem(`search_history_${userId}`);
      setHistory([]);
    } catch (error) {
      console.error('清除历史失败:', error);
    }
  };

  const handleSelect = (record: SearchRecord) => {
    if (onSelect) {
      onSelect(record);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in">
      <div className="bg-white dark:bg-dark-800 rounded-2xl shadow-2xl max-w-lg w-full max-h-[70vh] overflow-hidden flex flex-col animate-scale-in">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-gray-200 dark:border-dark-600">
          <h2 className="text-lg font-bold text-gray-900 dark:text-white font-display flex items-center gap-2">
            <Clock className="w-5 h-5 text-primary-500" />
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
        <div className="flex-1 overflow-y-auto p-5">
          {history.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Clock className="w-12 h-12 text-gray-300 dark:text-gray-600 mb-3" />
              <p className="text-gray-500 dark:text-gray-400 text-sm">暂无搜索历史</p>
            </div>
          ) : (
            <div className="space-y-2">
              {history.map((record, index) => (
                <button
                  key={index}
                  onClick={() => handleSelect(record)}
                  className="w-full text-left flex items-center gap-3 px-4 py-3 rounded-xl
                             bg-gray-50 dark:bg-dark-600/50 hover:bg-primary-50 dark:hover:bg-primary-900/20
                             border border-transparent hover:border-primary-200 dark:hover:border-primary-700
                             transition-all duration-200 group"
                >
                  <Search className="w-4 h-4 text-gray-400 group-hover:text-primary-500 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                      {record.keyword}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500">
                      返回 {record.topK} 个 · {formatRelativeTime(record.timestamp)}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        {history.length > 0 && (
          <div className="p-4 border-t border-gray-200 dark:border-dark-600">
            <button
              onClick={handleClearHistory}
              className="flex items-center gap-2 px-4 py-2 text-sm text-red-600 dark:text-red-400
                         hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors mx-auto"
            >
              <Trash2 className="w-4 h-4" />
              清除全部历史
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
