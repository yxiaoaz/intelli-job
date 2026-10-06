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
  Lightbulb,
  CheckCircle2,
  AlertTriangle,
  FileText,
  ArrowRight,
  Loader2,
} from 'lucide-react';
import { jobAPI } from '@/lib/api';
import { buttonClasses } from '@/components/ui/Button';

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
  const [aiExplanation, setAiExplanation] = useState<any>(null);
  const [loadingExplanation, setLoadingExplanation] = useState(false);

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

  // Load AI explanation
  useEffect(() => {
    if (!job?.id) return;
    let cancelled = false;
    setLoadingExplanation(true);
    jobAPI.getAIExplanation(job.id)
      .then((res) => {
        if (!cancelled) setAiExplanation(res.data);
      })
      .catch((err) => {
        if (!cancelled) console.error('Failed to load AI explanation:', err);
      })
      .finally(() => {
        if (!cancelled) setLoadingExplanation(false);
      });
    return () => { cancelled = true; };
  }, [job?.id]);

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
      <div className="min-h-screen flex items-center justify-center bg-base">
        <div className="loading-dots">
          <span></span><span></span><span></span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-base">
        <div className="text-center">
          <p className="text-tint-danger mb-4">{error}</p>
          <button
            onClick={handleBack}
            className={buttonClasses('primary', 'md')}
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
    <div className="min-h-screen bg-base">
      {/* Header */}
      <header className="bg-layer1 border-b border-l1 shadow-lv1 sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <button
            onClick={handleBack}
            className="flex items-center gap-2 text-700 hover:text-primary-600 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span>{from === 'chat' ? '返回对话' : '返回'}</span>
          </button>
          <button
            onClick={toggleBookmark}
            disabled={bookmarking}
            className="flex items-center gap-2 px-4 py-2 rounded-btn border border-l2 hover:bg-hover-neutral transition-colors disabled:opacity-50"
            title={bookmarked ? '取消收藏' : '收藏岗位'}
          >
            {bookmarked ? (
              <BookmarkCheck className="w-4 h-4 text-primary-500" />
            ) : (
              <Bookmark className="w-4 h-4 text-500" />
            )}
            <span className="text-sm font-medium text-700">
              {bookmarked ? '已收藏' : '收藏'}
            </span>
          </button>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
        {/* Title block */}
        <div className="bg-layer1 border border-l1 rounded-menu shadow-lv1 p-6">
          <h1 className="text-2xl font-medium text-900 mb-3 leading-tight">
            {job.title}
          </h1>
          <div className="flex items-center gap-4 text-sm text-500 flex-wrap">
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
          <div className="bg-layer1 border border-l1 rounded-menu p-4">
            <div className="flex items-center gap-2 mb-2">
              <Percent className="w-5 h-5 text-primary-500" />
              <h3 className="font-medium text-900">匹配度分析</h3>
            </div>
            <div className="flex items-center gap-3 mb-2">
              <div className="flex-1 bg-layer2 rounded-full h-2">
                <div
                  className="bg-primary-500 h-2 rounded-full transition-colors"
                  style={{ width: `${Math.min(Math.max(matchScore, 0), 100)}%` }}
                ></div>
              </div>
              <span className="text-sm font-medium text-primary-600">
                {matchScore.toFixed(1)}%
              </span>
            </div>
            <p className="text-xs text-500">
              匹配度来自当前对话搜索结果，仅供参考。
            </p>
          </div>
        )}

        {/* AI 申请建议 */}
        <div className="bg-layer1 border border-l1 rounded-menu p-4">
          <div className="flex items-center gap-2 mb-3">
            <Lightbulb className="w-5 h-5 text-primary-500" />
            <h3 className="font-medium text-900">AI 申请建议</h3>
          </div>
          {loadingExplanation ? (
            <div className="flex items-center gap-2 text-sm text-primary-500 py-3">
              <Loader2 className="w-4 h-4 animate-spin" />
              AI 正在分析匹配度...
            </div>
          ) : aiExplanation ? (
            <div className="space-y-3">
              {aiExplanation.match_reasons?.length > 0 && (
                <div className="space-y-1.5">
                  {aiExplanation.match_reasons.map((reason: string, idx: number) => (
                    <div key={idx} className="flex items-start gap-2 text-sm text-500">
                      <CheckCircle2 className="w-4 h-4 text-success-600 flex-shrink-0 mt-0.5" />
                      <span>{reason}</span>
                    </div>
                  ))}
                </div>
              )}
              {aiExplanation.match_risks?.length > 0 && (
                <div className="space-y-1.5">
                  {aiExplanation.match_risks.map((risk: string, idx: number) => (
                    <div key={idx} className="flex items-start gap-2 text-sm text-500">
                      <AlertTriangle className="w-4 h-4 text-warning-600 flex-shrink-0 mt-0.5" />
                      <span>{risk}</span>
                    </div>
                  ))}
                </div>
              )}
              {aiExplanation.resume_tips?.length > 0 && (
                <div className="pt-3 border-t border-l1">
                  <div className="flex items-center gap-1.5 text-sm font-medium text-primary-700 mb-2">
                    <FileText className="w-4 h-4" />
                    简历优化建议
                  </div>
                  <div className="space-y-2">
                    {aiExplanation.resume_tips.map((tip: any, idx: number) => (
                      <div key={idx} className="text-sm text-500">
                        <span className="text-400">「{tip.original}」</span>
                        <ArrowRight className="w-3.5 h-3.5 inline mx-1.5 text-primary-500" />
                        <span className="text-primary-700">{tip.suggested}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {aiExplanation.fallback_message && (
                <p className="text-sm text-400 italic">{aiExplanation.fallback_message}</p>
              )}
            </div>
          ) : (
            <p className="text-sm text-400 py-2">暂无 AI 分析结果</p>
          )}
        </div>

        {/* Job Description */}
        {job.full_description && (
          <div className="bg-layer1 border border-l1 rounded-menu shadow-lv1 p-6">
            <h3 className="font-medium text-900 mb-3 text-lg">职位描述</h3>
            <div className="text-sm text-700 whitespace-pre-wrap leading-relaxed space-y-2">
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
          <div className="text-xs text-500 px-2">
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
              className={buttonClasses('primary', 'md', 'flex-1')}
            >
              <ExternalLink className="w-4 h-4" />
              查看源网页
            </a>
          )}
          <button
            onClick={handleBack}
            className={buttonClasses('secondary', 'md')}
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
        <div className="min-h-screen flex items-center justify-center bg-base">
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
