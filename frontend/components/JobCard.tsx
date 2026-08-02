'use client';

import { useState } from 'react';
import { 
  MapPin, 
  Building2, 
  DollarSign, 
  Sparkles, 
  ArrowRight,
  Bookmark,
  BookmarkCheck,
  ExternalLink,
  TrendingUp,
  Briefcase,
  Clock
} from 'lucide-react';

interface JobCardProps {
  job: any;
  index: number;
  onClick: () => void;
  isBookmarked?: boolean;
  onBookmark?: () => void;
}

export default function JobCard({ job, index, onClick, isBookmarked = false, onBookmark }: JobCardProps) {
  const [isHovered, setIsHovered] = useState(false);

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

  // 匹配度颜色 — 增强版：绿/橙/红三色 + 左边框指示
  const getMatchColor = (score: number) => {
    if (score >= 70) return { gradient: 'from-green-500 to-emerald-500', border: 'border-l-green-500' };
    if (score >= 30) return { gradient: 'from-yellow-500 to-orange-500', border: 'border-l-orange-500' };
    return { gradient: 'from-red-400 to-red-500', border: 'border-l-red-500' };
  };

  // 公司颜色（基于公司名哈希）
  const getCompanyColor = (company: string) => {
    const colors = [
      'from-blue-600 to-indigo-600',
      'from-purple-600 to-pink-600',
      'from-orange-500 to-red-500',
      'from-green-500 to-teal-500',
      'from-cyan-500 to-blue-500',
    ];
    const hash = company.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
    return colors[hash % colors.length];
  };

  return (
    <div
      className={`
        relative overflow-hidden rounded-2xl border-2 transition-all duration-300 cursor-pointer group
        ${isHovered 
          ? 'border-primary-400 dark:border-primary-500 shadow-xl shadow-primary-500/20 -translate-y-1' 
          : 'border-gray-200 dark:border-gray-700 shadow-md hover:shadow-lg'
        }
        ${job.match_score != null ? `border-l-4 ${getMatchColor(job.match_score).border}` : ''}
        bg-white dark:bg-dark-700 animate-slide-up
      `}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={onClick}
      style={{ animationDelay: `${index * 100}ms` }}
    >
      {/* 顶部渐变条 */}
      <div className={`h-1 bg-gradient-to-r ${getCompanyColor(job.company || '')}`} />

      {/* 卡片内容 */}
      <div className="p-5">
        {/* 头部：排名徽章 + 收藏按钮 */}
        <div className="flex items-start justify-between mb-3">
          {/* 排名徽章 */}
          <div className="flex items-center gap-2">
            <div className={`
              w-8 h-8 rounded-full bg-gradient-to-br ${getCompanyColor(job.company || '')} 
              flex items-center justify-center text-white font-bold text-sm shadow-md
            `}>
              {index + 1}
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                推荐岗位
              </span>
            </div>
          </div>

          {/* 匹配度 + 收藏 */}
          <div className="flex items-center gap-2">
            {job.match_score && (
              <div className={`
                px-3 py-1 rounded-full text-xs font-bold text-white
                bg-gradient-to-r ${getMatchColor(job.match_score).gradient}
                shadow-sm flex items-center gap-1
              `}>
                <Sparkles className="w-3 h-3" />
                {job.match_score.toFixed(0)}%
              </div>
            )}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onBookmark?.();
              }}
              className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-600 transition-colors"
            >
              {isBookmarked ? (
                <BookmarkCheck className="w-4 h-4 text-primary-600 dark:text-primary-400" />
              ) : (
                <Bookmark className="w-4 h-4 text-gray-400 dark:text-gray-500" />
              )}
            </button>
          </div>
        </div>

        {/* 岗位标题 */}
        <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-2 group-hover:text-primary-600 dark:group-hover:text-primary-400 transition-colors line-clamp-1">
          {job.title}
        </h3>

        {/* 公司信息 */}
        <div className="flex items-center gap-2 mb-4">
          <Building2 className="w-4 h-4 text-gray-400 dark:text-gray-500 flex-shrink-0" />
          <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">
            {job.company}
          </span>
          {job.source && (
            <span className="text-xs px-2 py-0.5 bg-gray-100 dark:bg-dark-600 text-gray-500 dark:text-gray-400 rounded-md">
              {job.source}
            </span>
          )}
        </div>

        {/* 关键信息网格 */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          {/* 地点 */}
          <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
            <MapPin className="w-4 h-4 text-gray-400 flex-shrink-0" />
            <span className="truncate">{job.location || '未指定'}</span>
          </div>

          {/* 薪资 */}
          <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
            <DollarSign className="w-4 h-4 text-gray-400 flex-shrink-0" />
            <span className="font-semibold text-green-600 dark:text-green-400">
              {formatSalary()}
            </span>
          </div>

          {/* 经验要求 */}
          {job.experience && (
            <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
              <Briefcase className="w-4 h-4 text-gray-400 flex-shrink-0" />
              <span className="truncate">{job.experience}</span>
            </div>
          )}

          {/* 学历要求 */}
          {job.education && (
            <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
              <TrendingUp className="w-4 h-4 text-gray-400 flex-shrink-0" />
              <span className="truncate">{job.education}</span>
            </div>
          )}
        </div>

        {/* 岗位描述（截断版） */}
        {job.truncated_description && (
          <div className="mb-4">
            <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-2 leading-relaxed">
              {job.truncated_description}
            </p>
          </div>
        )}

        {/* 技能标签（如果有） */}
        {job.skills && job.skills.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {job.skills.slice(0, 3).map((skill: string, idx: number) => (
              <span
                key={idx}
                className="px-2 py-1 text-xs font-medium bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400 rounded-md border border-primary-200 dark:border-primary-800"
              >
                {skill}
              </span>
            ))}
            {job.skills.length > 3 && (
              <span className="px-2 py-1 text-xs text-gray-500 dark:text-gray-400">
                +{job.skills.length - 3}
              </span>
            )}
          </div>
        )}

        {/* 底部操作栏 */}
        <div className="flex items-center justify-between pt-3 border-t border-gray-100 dark:border-gray-700">
          <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
            <Clock className="w-3 h-3" />
            <span>刚刚发布</span>
          </div>
          
          <div className="flex items-center gap-1 text-sm font-medium text-primary-600 dark:text-primary-400 group-hover:gap-2 transition-all">
            <span>查看详情</span>
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </div>
        </div>
      </div>

      {/* 悬停时的光晕效果 */}
      {isHovered && (
        <div className="absolute inset-0 bg-gradient-to-br from-primary-500/5 to-transparent pointer-events-none" />
      )}
    </div>
  );
}
