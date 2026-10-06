'use client';

import { useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Bookmark,
  BookmarkCheck,
  TrendingUp,
  Briefcase,
  Clock,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
  Lightbulb,
  Loader2,
  FileText,
  ArrowRight
} from 'lucide-react';
import { formatRelativeTime } from '@/lib/time';
import { recruitmentTypeLabels } from '@/lib/constants';
import { jobAPI } from '@/lib/api';
import { buttonClasses } from '@/components/ui/Button';

interface JobCardProps {
  job: any;
  index: number;
  onViewDetail: () => void;
  isBookmarked?: boolean;
  onBookmark?: () => void;
  /** 标记已投递（站内状态）；未传则不渲染该按钮（向后兼容） */
  onMarkApplied?: () => void;
  /** 派生自 useBookmark 的 statusMap：getStatus 非 saved 非 null 即 'applied' */
  applyState?: 'none' | 'applied';
}

export default function JobCard({ job, index, onViewDetail, isBookmarked = false, onBookmark, onMarkApplied, applyState = 'none' }: JobCardProps) {
  const [reasonExpanded, setReasonExpanded] = useState(false);
  const [aiExplanation, setAiExplanation] = useState<any>(null);
  const [loadingExplanation, setLoadingExplanation] = useState(false);
  const [showExplanation, setShowExplanation] = useState(false);

  const handleAIExplanation = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (aiExplanation) {
      setShowExplanation((v) => !v);
      return;
    }
    setLoadingExplanation(true);
    setShowExplanation(true);
    try {
      const res = await jobAPI.getAIExplanation(job.id);
      setAiExplanation(res.data);
    } catch (err) {
      console.error('Failed to get AI explanation:', err);
    } finally {
      setLoadingExplanation(false);
    }
  };

  // 匹配度色（决策 2 语义色：success / warning / danger，深浅主题同一档，无需 dark: 分支）
  const getMatchColor = (score: number) => {
    if (score >= 70) return 'text-success-600';
    if (score >= 30) return 'text-warning-600';
    return 'text-danger-600';
  };

  const getMatchBg = (score: number) => {
    if (score >= 70) return 'bg-success-400';
    if (score >= 30) return 'bg-warning-400';
    return 'bg-danger-400';
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

  // 发布时间距今 > 60 天视为陈旧岗位
  const isStaleJob = (() => {
    if (!job.update_time) return false;
    const diff = Date.now() - new Date(job.update_time).getTime();
    return diff > 60 * 24 * 60 * 60 * 1000;
  })();

  // 无有效简历匹配时（分数 < 10）不展示红色低分，避免打击信心
  const validScore = job.match_score != null && job.match_score >= 10 ? job.match_score : null;

  // 地址显示归一：只保留到市/区一级，街道/门牌/邮编进详情展示
  const formatLocation = (loc?: string | null): string => {
    if (!loc) return '未指定';
    if (loc.includes('/')) {
      const parts = loc.split('/').filter(Boolean);
      return parts.slice(-2).join(' ');
    }
    const cleaned = loc.replace(/^.*?(?:省|自治区)/, '');
    const cityToDistrict = cleaned.match(/^[^市]*?市.*?[区县]/);
    if (cityToDistrict) return cityToDistrict[0];
    const cityOnly = cleaned.match(/^[^市]*?市/);
    if (cityOnly) return cityOnly[0];
    return cleaned.length > 12 ? cleaned.slice(0, 12) + '…' : cleaned;
  };

  return (
    <div
      className="
        rounded-menu border border-l1 bg-layer1
        transition-shadow duration-base ease-ds hover:shadow-lv1
      "
    >
      <div className="p-4">
        {/* Top row: title + match score */}
        <div className="flex items-start justify-between mb-2">
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-medium text-900 truncate">
              {job.title}
            </h3>
            <p className="text-xs text-500 mt-0.5">
              {job.company} · {formatLocation(job.location)}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0 ml-3">
            {validScore != null ? (
              <span className={`text-sm font-medium ${getMatchColor(validScore)}`}>
                {validScore.toFixed(0)}%
              </span>
            ) : job.match_score != null ? (
              <span className="text-sm font-medium text-400">—</span>
            ) : null}
            {isStaleJob && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-input font-medium bg-layer2 text-500">
                信息可能已过期
              </span>
            )}
            {job.tags?.map((tag: any, i: number) => (
              <span
                key={i}
                className={`text-[10px] px-1.5 py-0.5 rounded-input font-medium ${
                  tag.type === 'hot'
                    ? 'bg-tint-danger text-danger-600'
                    : 'bg-tint-primary text-primary-600'
                }`}
              >
                {tag.text}
              </span>
            ))}
          </div>
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-3 text-xs text-500 mb-3 flex-wrap">
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
              className="flex items-center gap-1 text-400"
              title={`发布时间：${job.update_time}`}
            >
              <Clock className="w-3 h-3" />
              {formatRelativeTime(job.update_time)}
              {isNewJob && (
                <span className="ml-0.5 px-1 py-px rounded-input text-[9px] font-medium bg-tint-warning text-warning-600">
                  新职位
                </span>
              )}
            </span>
          )}
          {job.recruitment_type && recruitmentTypeLabels[job.recruitment_type] && (
            <span className="px-1.5 py-0.5 rounded-input text-[10px] font-medium bg-layer2 text-700">
              {recruitmentTypeLabels[job.recruitment_type]}
            </span>
          )}
        </div>

        {/* Match score bar（无有效匹配时不展示） */}
        {validScore != null && (
          <div className="flex items-center gap-2 mb-2">
            <div className="flex-1 max-w-[120px] h-1.5 bg-layer2 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-colors duration-slow ease-ds ${getMatchBg(validScore)}`}
                style={{ width: `${validScore}%` }}
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
                className="px-2 py-0.5 text-[11px] font-medium bg-layer2 text-700 rounded-input"
              >
                {skill}
              </span>
            ))}
            {job.skills.length > 4 && (
              <span className="px-1.5 py-0.5 text-[11px] text-400">
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
              className="flex items-center gap-1 text-xs text-primary-600 hover:text-primary-800 transition-colors duration-base ease-ds mt-1"
            >
              {reasonExpanded ? '收起匹配详情' : '查看匹配详情'}
              {reasonExpanded ? (
                <ChevronUp className="w-3 h-3" />
              ) : (
                <ChevronDown className="w-3 h-3" />
              )}
            </button>
            <div
              className={`overflow-hidden transition-colors duration-slow ease-ds ${
                reasonExpanded ? 'max-h-48 opacity-100 mt-2' : 'max-h-0 opacity-0'
              }`}
            >
              <div className="p-2.5 bg-layer2 rounded-input space-y-1">
                {matchReasons.map((reason: string, idx: number) => (
                  <div key={idx} className="flex items-start gap-1.5 text-xs text-700">
                    <CheckCircle2 className="w-3 h-3 text-success-600 flex-shrink-0 mt-0.5" />
                    <span>{reason}</span>
                  </div>
                ))}
                {matchRisks.map((risk: string, idx: number) => (
                  <div key={idx} className="flex items-start gap-1.5 text-xs text-700">
                    <AlertTriangle className="w-3 h-3 text-warning-600 flex-shrink-0 mt-0.5" />
                    <span>{risk}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {/* AI 解释区域 */}
        {showExplanation && (
          <div className="overflow-hidden transition-colors duration-slow ease-ds mt-2">
            {loadingExplanation ? (
              <div className="p-3 bg-tint-primary rounded-input flex items-center gap-2 text-xs text-primary-600">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                AI 正在分析匹配度...
              </div>
            ) : aiExplanation ? (
              <div className="p-3 bg-tint-primary rounded-input space-y-2">
                {/* 匹配原因 */}
                {aiExplanation.match_reasons?.length > 0 && (
                  <div className="space-y-1">
                    {aiExplanation.match_reasons.map((reason: string, idx: number) => (
                      <div key={idx} className="flex items-start gap-1.5 text-xs text-700">
                        <CheckCircle2 className="w-3 h-3 text-success-600 flex-shrink-0 mt-0.5" />
                        <span>{reason}</span>
                      </div>
                    ))}
                  </div>
                )}
                {/* 风险/差距 */}
                {aiExplanation.match_risks?.length > 0 && (
                  <div className="space-y-1">
                    {aiExplanation.match_risks.map((risk: string, idx: number) => (
                      <div key={idx} className="flex items-start gap-1.5 text-xs text-700">
                        <AlertTriangle className="w-3 h-3 text-warning-600 flex-shrink-0 mt-0.5" />
                        <span>{risk}</span>
                      </div>
                    ))}
                  </div>
                )}
                {/* 简历建议 */}
                {aiExplanation.resume_tips?.length > 0 && (
                  <div className="pt-2 border-t border-l1">
                    <div className="flex items-center gap-1 text-xs font-medium text-primary-700 mb-1.5">
                      <FileText className="w-3 h-3" />
                      简历建议
                    </div>
                    {aiExplanation.resume_tips.map((tip: any, idx: number) => (
                      <div key={idx} className="text-xs text-700 mb-1.5 last:mb-0">
                        <span className="text-400">「{tip.original}」</span>
                        <ArrowRight className="w-3 h-3 inline mx-1 text-primary-500" />
                        <span className="text-primary-700">{tip.suggested}</span>
                      </div>
                    ))}
                  </div>
                )}
                {/* 降级提示 */}
                {aiExplanation.fallback_message && (
                  <div className="text-xs text-400 italic">
                    {aiExplanation.fallback_message}
                  </div>
                )}
              </div>
            ) : null}
          </div>
        )}

        {/* Action buttons — 决策 7：列表卡片行内按钮全部走 secondary/ghost，
            保证「任一视图 primary 实底按钮 ≤1」（primary CTA 留给页面级动作） */}
        <div className="flex items-center gap-2 mt-3 pt-3 border-t border-l1">
          <button onClick={onViewDetail} className={buttonClasses('secondary', 'sm')}>
            查看详情
          </button>
          <button onClick={handleAIExplanation} className={buttonClasses('secondary', 'sm')}>
            {loadingExplanation ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <Lightbulb className="w-3 h-3" />
            )}
            {showExplanation && aiExplanation ? '收起' : 'AI 解释'}
          </button>
          {onBookmark && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onBookmark?.();
              }}
              className={buttonClasses('secondary', 'sm')}
            >
              {isBookmarked ? <BookmarkCheck className="w-3 h-3" /> : <Bookmark className="w-3 h-3" />}
              {isBookmarked ? '已收藏' : '收藏'}
            </button>
          )}
          {onMarkApplied && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onMarkApplied();
              }}
              className={buttonClasses(
                'secondary',
                'sm',
                applyState === 'applied' ? 'border-success-400 text-success-600' : undefined
              )}
            >
              {applyState === 'applied' && <CheckCircle2 className="w-3 h-3" />}
              {applyState === 'applied' ? '已投递' : '标记已投递'}
            </button>
          )}
          {job.url && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                window.open(job.url, '_blank');
              }}
              className={buttonClasses('ghost', 'sm', 'ml-auto text-500 hover:text-primary-600')}
              title="跳转到源站投递"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              去源站
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
