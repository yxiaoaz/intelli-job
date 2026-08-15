'use client';

import { Suspense, useEffect, useState } from 'react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  ExternalLink,
  Bookmark,
  BookmarkCheck,
  MapPin,
  Briefcase,
  Percent,
  Building2,
  Calendar,
  GraduationCap,
} from 'lucide-react';

function JobDetailContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();

  const id = params.id as string;
  const matchScoreParam = searchParams.get('matchScore');
  const from = searchParams.get('from');
  const matchScore = matchScoreParam ? parseFloat(matchScoreParam) : null;

  const [job, setJob] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [bookmarked, setBookmarked] = useState(false);
  const [bookmarking, setBookmarking] = useState(false);

  useEffect(() => {
    const fetchJob = async () => {
      try {
        setLoading(true);
        const token = localStorage.getItem('access_token');
        const res = await fetch(`/api/v1/jobs/${id}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.status === 401) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          router.push('/login');
          return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setJob(data);
        setBookmarked(data.is_bookmarked ?? false);
      } catch (e: any) {
        setError(e.message || '加载岗位详情失败');
      } finally {
        setLoading(false);
      }
    };
    fetchJob();
  }, [id, router]);

  const handleBack = () => {
    if (from === 'chat') {
      router.push('/chat');
    } else {
      router.back();
    }
  };

  const toggleBookmark = async () => {
    try {
      setBookmarking(true);
      const token = localStorage.getItem('access_token');
      const res = await fetch(`/api/v1/jobs/bookmarks/${id}`, {
        method: bookmarked ? 'DELETE' : 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setBookmarked(!bookmarked);
    } catch (err) {
      console.error('Failed to toggle bookmark:', err);
    } finally {
      setBookmarking(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-dark-50 via-white to-primary-50 dark:from-dark-900 dark:via-dark-800 dark:to-dark-900">
        <div className="loading-dots">
          <span></span><span></span><span></span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-dark-50 via-white to-primary-50 dark:from-dark-900 dark:via-dark-800 dark:to-dark-900">
        <div className="text-center">
          <p className="text-red-600 dark:text-red-400 mb-4">{error}</p>
          <button
            onClick={handleBack}
            className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
          >
            返回
          </button>
        </div>
      </div>
    );
  }

  if (!job) return null;

  // 把 ISO 时间格式化为 YYYY-MM-DD（本地时区，避免 toISOString 跨日偏差）
  const updateDateText = job.update_time
    ? (() => {
        const d = new Date(job.update_time);
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      })()
    : null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-dark-50 via-white to-primary-50 dark:from-dark-900 dark:via-dark-800 dark:to-dark-900">
      {/* Header */}
      <header className="glass shadow-md sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <button
            onClick={handleBack}
            className="flex items-center gap-2 text-gray-700 dark:text-gray-300 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span>{from === 'chat' ? '返回对话' : '返回'}</span>
          </button>
          <button
            onClick={toggleBookmark}
            disabled={bookmarking}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-primary-200 dark:border-primary-700 hover:bg-primary-50 dark:hover:bg-dark-700 transition-colors disabled:opacity-50"
            title={bookmarked ? '取消收藏' : '收藏岗位'}
          >
            {bookmarked ? (
              <BookmarkCheck className="w-4 h-4 text-primary-600 dark:text-primary-400" />
            ) : (
              <Bookmark className="w-4 h-4 text-gray-500 dark:text-gray-400" />
            )}
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {bookmarked ? '已收藏' : '收藏'}
            </span>
          </button>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
        {/* Title block */}
        <div className="glass rounded-2xl shadow-md p-6 border border-primary-200/50 dark:border-primary-700/50">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-3 leading-tight">
            {job.title}
          </h1>
          <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400 flex-wrap">
            <div className="flex items-center gap-1">
              <Building2 className="w-4 h-4 flex-shrink-0" />
              <span>{job.company}</span>
            </div>
            <div className="flex items-center gap-1">
              <MapPin className="w-4 h-4 flex-shrink-0" />
              <span>{job.location}</span>
            </div>
            <div className="flex items-center gap-1">
              <Briefcase className="w-4 h-4 flex-shrink-0" />
              <span>{job.recruitment_type || '未知'}</span>
            </div>
            <div className="flex items-center gap-1">
              <GraduationCap className="w-4 h-4 flex-shrink-0" />
              <span>{job.education || '不限'}</span>
            </div>
            {updateDateText && (
              <div className="flex items-center gap-1">
                <Calendar className="w-4 h-4 flex-shrink-0" />
                <span>更新于 {updateDateText}</span>
              </div>
            )}
          </div>
        </div>

        {/* Match Analysis — only when carried over from chat card */}
        {matchScore !== null && !Number.isNaN(matchScore) && (
          <div className="glass rounded-xl p-4 border border-primary-200/50 dark:border-primary-700/50">
            <div className="flex items-center gap-2 mb-2">
              <Percent className="w-5 h-5 text-primary-600 dark:text-primary-400" />
              <h3 className="font-semibold text-gray-900 dark:text-white">匹配度分析</h3>
            </div>
            <div className="flex items-center gap-3 mb-2">
              <div className="flex-1 bg-gray-200 dark:bg-dark-600 rounded-full h-2">
                <div
                  className="bg-gradient-to-r from-primary-600 to-primary-500 h-2 rounded-full transition-all"
                  style={{ width: `${Math.min(Math.max(matchScore, 0), 100)}%` }}
                ></div>
              </div>
              <span className="text-sm font-bold text-primary-600 dark:text-primary-400">
                {matchScore.toFixed(1)}%
              </span>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              匹配度来自当前对话搜索结果，仅供参考。
            </p>
          </div>
        )}

        {/* Job Description */}
        {job.full_description && (
          <div className="glass rounded-2xl shadow-md p-6 border border-primary-200/50 dark:border-primary-700/50">
            <h3 className="font-semibold text-gray-900 dark:text-white mb-3 text-lg">职位描述</h3>
            <div className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap leading-relaxed space-y-2">
              {job.full_description.split('\n').map((paragraph: string, idx: number) => (
                <p key={idx} className="min-h-[1.5em]">
                  {paragraph || '\u00A0'}
                </p>
              ))}
            </div>
          </div>
        )}

        {/* Source Info */}
        {job.source && (
          <div className="text-xs text-gray-500 dark:text-gray-400 px-2">
            数据来源：{job.source}
          </div>
        )}

        {/* Footer Actions */}
        <div className="flex gap-3 pt-2">
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
            onClick={handleBack}
            className="px-6 py-3 bg-gray-200 dark:bg-dark-600 text-gray-700 dark:text-gray-300 rounded-xl hover:bg-gray-300 dark:hover:bg-dark-500 transition-all font-medium"
          >
            {from === 'chat' ? '返回对话' : '返回'}
          </button>
        </div>
      </main>
    </div>
  );
}

export default function JobDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-dark-50 via-white to-primary-50 dark:from-dark-900 dark:via-dark-800 dark:to-dark-900">
          <div className="loading-dots">
            <span></span><span></span><span></span>
          </div>
        </div>
      }
    >
      <JobDetailContent />
    </Suspense>
  );
}
