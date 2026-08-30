'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { X, Bookmark, Trash2, ExternalLink, ArrowRight } from 'lucide-react';
import { jobAPI } from '@/lib/api';
import { formatMonthDay } from '@/lib/time';
import { toast } from 'sonner';

interface FavoritesModalProps {
  isOpen: boolean;
  onClose: () => void;
}

// 与后端 ApplicationStatus 枚举一致
const STATUS_OPTIONS = [
  { value: 'saved', label: '已收藏' },
  { value: 'applied', label: '已投递' },
  { value: 'interviewing', label: '面试中' },
  { value: 'rejected', label: '已拒绝' },
  { value: 'accepted', label: '已录用' },
] as const;

interface BookmarkItem {
  id: string;
  job_id: string;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string | null;
  job: {
    id: string;
    title: string;
    company: string;
    location: string;
    salary: string;
    url?: string;
  };
}

export default function FavoritesModal({ isOpen, onClose }: FavoritesModalProps) {
  const router = useRouter();
  const [favorites, setFavorites] = useState<BookmarkItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [removing, setRemoving] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadFavorites();
    }
  }, [isOpen]);

  const loadFavorites = async () => {
    try {
      setLoading(true);
      const response = await jobAPI.bookmarks.getList();
      setFavorites(response.data || []);
    } catch (error) {
      console.error('加载收藏列表失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRemove = async (jobId: string) => {
    if (!confirm('确定要取消收藏这个职位吗？')) return;

    try {
      setRemoving(jobId);
      await jobAPI.bookmarks.remove(jobId);
      setFavorites(favorites.filter(f => f.job_id !== jobId));
    } catch (error) {
      console.error('取消收藏失败:', error);
      toast.error('取消收藏失败，请重试');
    } finally {
      setRemoving(null);
    }
  };

  /** 状态下拉：乐观更新 + PATCH，失败回滚 + toast（与看板页同款逻辑） */
  const handleStatusChange = async (item: BookmarkItem, nextStatus: string) => {
    const prevStatus = item.status;
    if (prevStatus === nextStatus) return;
    setFavorites((prev) =>
      prev.map((f) => (f.job_id === item.job_id ? { ...f, status: nextStatus } : f))
    );
    try {
      const res = await jobAPI.bookmarks.update(item.job_id, { status: nextStatus });
      setFavorites((prev) =>
        prev.map((f) => (f.job_id === item.job_id ? { ...f, ...res.data } : f))
      );
    } catch (error) {
      setFavorites((prev) =>
        prev.map((f) => (f.job_id === item.job_id ? { ...f, status: prevStatus } : f))
      );
      console.error('状态更新失败:', error);
      toast.error('状态更新失败，请重试');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in">
      <div className="bg-white dark:bg-dark-800 rounded-2xl shadow-2xl max-w-4xl w-full max-h-[80vh] overflow-hidden flex flex-col animate-scale-in">
        
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-dark-600">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white font-display">
              我的收藏
            </h2>
            <button
              onClick={() => {
                onClose();
                router.push('/bookmarks');
              }}
              className="mt-1 text-sm text-primary-600 dark:text-primary-400
                         hover:text-primary-700 dark:hover:text-primary-300 transition-colors
                         flex items-center gap-1"
            >
              进入求职看板
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
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
          ) : favorites.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Bookmark className="w-16 h-16 text-gray-300 dark:text-gray-600 mb-4" />
              <p className="text-gray-500 dark:text-gray-400">暂无收藏职位</p>
            </div>
          ) : (
            <div className="space-y-4">
              {favorites.map((item) => (
                <div
                  key={item.id}
                  className="glass rounded-xl p-4 border border-primary-200/50 dark:border-primary-700/50 card-hover"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                        {item.job.title}
                      </h3>
                      <div className="space-y-1 text-sm text-gray-700 dark:text-gray-300">
                        <div>{item.job.company}</div>
                        <div>{item.job.location}</div>
                        <div>{item.job.salary || '面议'}</div>
                        <div className="text-xs text-gray-400 dark:text-gray-500">
                          收藏于 {formatMonthDay(item.created_at)}
                        </div>
                        {item.notes && (
                          <div className="text-xs text-gray-500 dark:text-gray-400">
                            备注：{item.notes}
                          </div>
                        )}
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      {/* 状态下拉（PATCH 同看板页） */}
                      <select
                        value={item.status}
                        onChange={(e) => handleStatusChange(item, e.target.value)}
                        className="text-xs font-medium rounded-lg border border-gray-200 dark:border-dark-500
                                   px-2 py-1.5 bg-white dark:bg-dark-700 cursor-pointer
                                   text-gray-700 dark:text-gray-200
                                   focus:outline-none focus:ring-2 focus:ring-primary-500/40"
                        aria-label="申请状态"
                      >
                        {STATUS_OPTIONS.map((s) => (
                          <option key={s.value} value={s.value}>
                            {s.label}
                          </option>
                        ))}
                      </select>
                      {item.job.url && (
                        <a
                          href={item.job.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-600 transition-colors"
                          title="查看职位详情"
                        >
                          <ExternalLink className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                        </a>
                      )}
                      <button
                        onClick={() => handleRemove(item.job_id)}
                        disabled={removing === item.job_id}
                        className="p-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50"
                        title="取消收藏"
                      >
                        <Trash2 className="w-5 h-5 text-red-600 dark:text-red-400" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 dark:border-dark-600">
          <button
            onClick={onClose}
            className="w-full px-6 py-3 bg-gradient-to-r from-primary-600 to-primary-500 text-white rounded-xl hover:from-primary-700 hover:to-primary-600 transition-all font-medium"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}
