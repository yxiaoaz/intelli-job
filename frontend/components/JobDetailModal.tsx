'use client';

import { useState } from 'react';
import { X, ExternalLink, Bookmark, BookmarkCheck, MapPin, DollarSign, Briefcase, Calendar, Percent } from 'lucide-react';

interface Job {
  id: string;
  title: string;
  company: string;
  location: string;
  salary_min?: number;
  salary_max?: number;
  salary_currency?: string;
  description?: string; // 截断版（用于卡片预览）
  full_description?: string; // 完整版（用于 Modal 详情）
  requirements?: string[];
  url?: string;
  source?: string;
  created_at?: string;
  match_score?: number;
  match_analysis?: string;
  [key: string]: any;
}

interface JobDetailModalProps {
  job: Job;
  isOpen: boolean;
  onClose: () => void;
  source?: 'dashboard' | 'chat';
}

export default function JobDetailModal({ job, isOpen, onClose, source = 'dashboard' }: JobDetailModalProps) {
  const [bookmarked, setBookmarked] = useState(false);
  const [bookmarking, setBookmarking] = useState(false);

  if (!isOpen) return null;

  const handleBookmark = async () => {
    try {
      setBookmarking(true);
      const token = localStorage.getItem('access_token');
      
      if (bookmarked) {
        // 取消收藏
        await fetch(`/api/v1/jobs/${job.id}/bookmark`, {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        setBookmarked(false);
      } else {
        // 添加收藏
        await fetch(`/api/v1/jobs/${job.id}/bookmark`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        setBookmarked(true);
      }
    } catch (err) {
      console.error('Failed to toggle bookmark:', err);
    } finally {
      setBookmarking(false);
    }
  };

  const formatSalary = (min?: number, max?: number, currency?: string) => {
    if (!min && !max) return '面议';
    const unit = currency === 'CNY' ? '元' : currency || '元';
    if (min && max) {
      return `${min / 1000}-${max / 1000}k/${unit}`;
    }
    if (min) {
      return `${min / 1000}k+/${unit}`;
    }
    if (max) {
      return `${max / 1000}k-/${unit}`;
    }
    return '面议';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in">
      {/* Modal Container */}
      <div className="bg-white dark:bg-dark-800 rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col animate-scale-in">
        
        {/* Header - 固定在顶部 */}
        <div className="flex-shrink-0 flex items-start justify-between p-6 border-b border-gray-200 dark:border-dark-600">
          <div className="flex-1 pr-4">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2 leading-tight">
              {job.title}
            </h2>
            <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400 flex-wrap">
              <div className="flex items-center gap-1">
                <Briefcase className="w-4 h-4 flex-shrink-0" />
                <span>{job.company}</span>
              </div>
              <div className="flex items-center gap-1">
                <MapPin className="w-4 h-4 flex-shrink-0" />
                <span>{job.location}</span>
              </div>
              <div className="flex items-center gap-1">
                <DollarSign className="w-4 h-4 flex-shrink-0" />
                <span>{formatSalary(job.salary_min, job.salary_max, job.salary_currency)}</span>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-2 flex-shrink-0">
            {/* Bookmark Button */}
            <button
              onClick={handleBookmark}
              disabled={bookmarking}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-600 transition-colors disabled:opacity-50"
              title={bookmarked ? '取消收藏' : '收藏'}
            >
              {bookmarked ? (
                <BookmarkCheck className="w-5 h-5 text-primary-600 dark:text-primary-400" />
              ) : (
                <Bookmark className="w-5 h-5 text-gray-600 dark:text-gray-400" />
              )}
            </button>

            {/* Close Button */}
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-600 transition-colors"
            >
              <X className="w-5 h-5 text-gray-600 dark:text-gray-400" />
            </button>
          </div>
        </div>

        {/* Content - 可滚动区域 */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          
          {/* Match Analysis (Chat 来源显示) */}
          {source === 'chat' && job.match_score !== undefined && (
            <div className="glass rounded-xl p-4 border border-primary-200/50 dark:border-primary-700/50">
              <div className="flex items-center gap-2 mb-2">
                <Percent className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                <h3 className="font-semibold text-gray-900 dark:text-white">匹配度分析</h3>
              </div>
              <div className="flex items-center gap-3 mb-2">
                <div className="flex-1 bg-gray-200 dark:bg-dark-600 rounded-full h-2">
                  <div 
                    className="bg-gradient-to-r from-primary-600 to-primary-500 h-2 rounded-full transition-all"
                    style={{ width: `${job.match_score}%` }}
                  ></div>
                </div>
                <span className="text-sm font-bold text-primary-600 dark:text-primary-400">
                  {job.match_score.toFixed(1)}%
                </span>
              </div>
              {job.match_analysis && (
                <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                  {job.match_analysis}
                </p>
              )}
            </div>
          )}

          {/* Job Description - 完整显示 */}
          {job.full_description && (
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-white mb-3 text-lg">职位描述</h3>
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <div className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap leading-relaxed space-y-2">
                  {job.full_description.split('\n').map((paragraph: string, idx: number) => (
                    <p key={idx} className="min-h-[1.5em]">
                      {paragraph || '\u00A0'}
                    </p>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Requirements */}
          {job.requirements && job.requirements.length > 0 && (
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-white mb-2">任职要求</h3>
              <ul className="space-y-1">
                {job.requirements.map((req, idx) => (
                  <li key={idx} className="text-sm text-gray-700 dark:text-gray-300 flex items-start gap-2">
                    <span className="text-primary-600 dark:text-primary-400 mt-1">•</span>
                    <span>{req}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Source Info */}
          {job.source && (
            <div className="text-xs text-gray-500 dark:text-gray-400">
              数据来源：{job.source}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 dark:border-dark-600 flex gap-3">
          {job.url && (
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-primary-600 to-primary-500 text-white rounded-xl hover:from-primary-700 hover:to-primary-600 transition-all font-medium shadow-lg hover:shadow-glow"
            >
              <ExternalLink className="w-4 h-4" />
              查看源网页
            </a>
          )}
          <button
            onClick={onClose}
            className="px-6 py-3 bg-gray-200 dark:bg-dark-600 text-gray-700 dark:text-gray-300 rounded-xl hover:bg-gray-300 dark:hover:bg-dark-500 transition-all font-medium"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}
