'use client';

import { useState } from 'react';
import { 
  MapPin, 
  Building2, 
  DollarSign, 
  Sparkles, 
  ChevronDown,
  ChevronUp,
  Bookmark,
  BookmarkCheck,
  TrendingUp,
  Briefcase,
  Clock,
  CheckCircle2,
  AlertTriangle,
  ExternalLink
} from 'lucide-react';
import { formatRelativeTime } from '@/lib/time';
import { recruitmentTypeLabels } from '@/lib/constants';

interface JobCardProps {
  job: any;
  index: number;
  onViewDetail: () => void;
  isBookmarked?: boolean;
  onBookmark?: () => void;
  onApply?: () => void;
}

export default function JobCard({ job, index, onViewDetail, isBookmarked = false, onBookmark, onApply }: JobCardProps) {
  const [reasonExpanded, setReasonExpanded] = useState(false);

  // 解析薪资显示
  const formatSalary = () => {
    if (!job.salary_min && !job.salary_max) return '薪资面议';
    const min = job.salary_min ? Math.floor(job.salary_min / 1000) : null;
    const max = job.salary_max ? Math.floor(job.salary_max / 1000) : null;
    
    if (min && max) return `${min}-${max}k`;
    if (min) return `${min}k+`;
    if (max) return `<${max}k`;
    return '薪资面议';
  };

  // 匹配度颜色
  const getMatchColor = (score: number) => {
    if (score >= 70) return 'text-emerald-600 dark:text-emerald-400';
    if (score >= 30) return 'text-amber-600 dark:text-amber-400';
    return 'text-red-500 dark:text-red-400';
  };

  const getMatchBg = (score: number) => {
    if (score >= 70) return 'bg-emerald-500';
    if (score >= 30) return 'bg-amber-500';
    return 'bg-red-500';
  };

  // Parse match reasons from job data
  const matchReasons = job.match_reasons || [];
  const matchRisks = job.match_risks || [];

  // 发布时间距今 <= 3 天视为新职位
  const isNewJob = (() => {
    if (!job.update_time) return false;
    const diff = Date.now() - new Date(job.update_time).getTime();
    return diff >= 0 && diff <= 3 * 24 * 60 * 60 * 1000;
  })();

  return (
    <div
      className="
        rounded-xl border border-gray-200 dark:border-dark-600
        bg-white dark:bg-dark-700 transition-all duration-200
        hover:border-primary-300 dark:hover:border-primary-600
        hover:shadow-md animate-slide-up
      "
      style={{ animationDelay: `${index * 80}ms` }}
    >
      <div className="p-4">
        {/* Top row: title + match score */}
        <div className="flex items-start justify-between mb-2">
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white truncate">
              {job.title}
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              {job.company} · {job.location || '未指定'}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0 ml-3">
            {job.match_score != null && (
              <span className={`text-sm font-bold ${getMatchColor(job.match_score)}`}>
                {job.match_score.toFixed(0)}%
              </span>
            )}
            {job.tags?.map((tag: any, i: number) => (
              <span
                key={i}
                className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  tag.type === 'hot'
                    ? 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400'
                    : 'bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400'
                }`}
              >
                {tag.text}
              </span>
            ))}
          </div>
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400 mb-3 flex-wrap">
          <span className="flex items-center gap-1">
            <DollarSign className="w-3 h-3" />
            <span className="font-semibold text-green-600 dark:text-green-400">{formatSalary()}</span>
          </span>
          {job.experience && (
            <span className="flex items-center gap-1">
              <Briefcase className="w-3 h-3" />
              {job.experience}
            </span>
          )}
          {job.education && (
            <span className="flex items-center gap-1">
              <TrendingUp className="w-3 h-3" />
              {job.education}
            </span>
          )}
          {job.update_time && (
            <span
              className="flex items-center gap-1 text-gray-400 dark:text-gray-500"
              title={`发布时间：${job.update_time}`}
            >
              <Clock className="w-3 h-3" />
              {formatRelativeTime(job.update_time)}
              {isNewJob && (
                <span className="ml-0.5 px-1 py-px rounded text-[9px] font-bold bg-orange-100 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400">
                  新职位
                </span>
              )}
            </span>
          )}
          {job.recruitment_type && recruitmentTypeLabels[job.recruitment_type] && (
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
              job.recruitment_type === 'EXPERIENCED' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300' :
              job.recruitment_type === 'GRADUATE' ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300' :
              'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300'
            }`}>
              {recruitmentTypeLabels[job.recruitment_type]}
            </span>
          )}
        </div>

        {/* Match score bar */}
        {job.match_score != null && (
          <div className="flex items-center gap-2 mb-2">
            <div className="flex-1 max-w-[120px] h-1.5 bg-gray-100 dark:bg-dark-600 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${getMatchBg(job.match_score)}`}
                style={{ width: `${job.match_score}%` }}
              />
            </div>
          </div>
        )}

        {/* Skills tags */}
        {job.skills && job.skills.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-3">
            {job.skills.slice(0, 4).map((skill: string, idx: number) => (
              <span
                key={idx}
                className="px-2 py-0.5 text-[11px] font-medium bg-gray-100 dark:bg-dark-600 text-gray-600 dark:text-gray-400 rounded-md"
              >
                {skill}
              </span>
            ))}
            {job.skills.length > 4 && (
              <span className="px-1.5 py-0.5 text-[11px] text-gray-400">
                +{job.skills.length - 4}
              </span>
            )}
          </div>
        )}

        {/* Match reason toggle */}
        {(matchReasons.length > 0 || matchRisks.length > 0) && (
          <>
            <button
              onClick={() => setReasonExpanded((v) => !v)}
              className="flex items-center gap-1 text-xs text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 transition-colors mt-1"
            >
              {reasonExpanded ? '收起匹配详情' : '查看匹配详情'}
              {reasonExpanded ? (
                <ChevronUp className="w-3 h-3" />
              ) : (
                <ChevronDown className="w-3 h-3" />
              )}
            </button>
            <div
              className={`overflow-hidden transition-all duration-300 ease-in-out ${
                reasonExpanded ? 'max-h-48 opacity-100 mt-2' : 'max-h-0 opacity-0'
              }`}
            >
              <div className="p-2.5 bg-gray-50 dark:bg-dark-800 rounded-lg space-y-1">
                {matchReasons.map((reason: string, idx: number) => (
                  <div key={idx} className="flex items-start gap-1.5 text-xs text-gray-600 dark:text-gray-400">
                    <CheckCircle2 className="w-3 h-3 text-emerald-500 flex-shrink-0 mt-0.5" />
                    <span>{reason}</span>
                  </div>
                ))}
                {matchRisks.map((risk: string, idx: number) => (
                  <div key={idx} className="flex items-start gap-1.5 text-xs text-gray-600 dark:text-gray-400">
                    <AlertTriangle className="w-3 h-3 text-amber-500 flex-shrink-0 mt-0.5" />
                    <span>{risk}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-100 dark:border-dark-600">
          <button
            onClick={onViewDetail}
            className="px-3 py-1.5 text-xs font-medium rounded-md border border-gray-200 dark:border-dark-500
                       text-gray-600 dark:text-gray-400 hover:border-primary-400 hover:text-primary-600
                       dark:hover:border-primary-500 dark:hover:text-primary-400 transition-colors"
          >
            查看详情
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onBookmark?.();
            }}
            className="px-3 py-1.5 text-xs font-medium rounded-md border border-gray-200 dark:border-dark-500
                       text-gray-600 dark:text-gray-400 hover:border-primary-400 hover:text-primary-600
                       dark:hover:border-primary-500 dark:hover:text-primary-400 transition-colors
                       flex items-center gap-1"
          >
            {isBookmarked ? (
              <BookmarkCheck className="w-3 h-3" />
            ) : (
              <Bookmark className="w-3 h-3" />
            )}
            收藏
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onApply?.();
            }}
            className="px-3 py-1.5 text-xs font-medium rounded-md
                       bg-primary-600 text-white hover:bg-primary-700 transition-colors"
          >
            准备投递
          </button>
          {job.url && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                window.open(job.url, '_blank');
              }}
              className="ml-auto px-2 py-1.5 text-xs rounded-md text-gray-400 hover:text-primary-500
                         dark:hover:text-primary-400 transition-colors flex items-center gap-1"
              title="查看原始职位"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              原链接
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
