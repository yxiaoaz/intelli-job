'use client';

import { useEffect, useState } from 'react';
import { X, DollarSign, Briefcase, Bookmark, Send, CheckCircle2, AlertTriangle, FileText, ArrowRight, Loader2, Lightbulb } from 'lucide-react';
import { jobAPI } from '@/lib/api';
import Button from '@/components/ui/Button';

interface JobDetailModalProps {
  job: any | null;
  onClose: () => void;
  onApply?: () => void;
  onBookmark?: () => void;
}

export default function JobDetailModal({ job, onClose, onApply, onBookmark }: JobDetailModalProps) {
  const [aiExplanation, setAiExplanation] = useState<any>(null);
  const [loadingExplanation, setLoadingExplanation] = useState(false);

  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  // Load AI explanation when job changes
  useEffect(() => {
    if (!job?.id) return;
    let cancelled = false;
    setLoadingExplanation(true);
    jobAPI.getAIExplanation(job.id)
      .then((res) => {
        if (!cancelled) setAiExplanation(res.data);
      })
      .catch((err) => {
        console.error('Failed to load AI explanation:', err);
      })
      .finally(() => {
        if (!cancelled) setLoadingExplanation(false);
      });
    return () => { cancelled = true; };
  }, [job?.id]);

  if (!job) return null;

  const formatSalary = () => {
    if (!job.salary_min && !job.salary_max) return '薪资面议';
    const min = job.salary_min ? Math.floor(job.salary_min / 1000) : null;
    const max = job.salary_max ? Math.floor(job.salary_max / 1000) : null;
    if (min && max) return `${min}-${max}k/月`;
    if (min) return `${min}k+/月`;
    if (max) return `<${max}k/月`;
    return '薪资面议';
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 transition-opacity"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-layer1 border border-l1 rounded-dialog w-[520px] max-h-[80vh] shadow-lv3 flex flex-col animate-fade-in">
        {/* Header */}
        <div className="px-6 pt-5 pb-4 border-b border-l1 flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-medium text-900 truncate">{job.title}</h2>
            <p className="text-sm text-500 mt-1">
              {job.company} · {job.location || '未指定'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-input flex items-center justify-center text-400 hover:bg-hover-neutral hover:text-700 transition-colors flex-shrink-0 ml-3"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {/* Salary + meta */}
          <div className="flex items-center gap-4 text-sm">
            <span className="flex items-center gap-1.5 text-success-600 font-medium">
              <DollarSign className="w-4 h-4" />
              {formatSalary()}
            </span>
            {job.experience && (
              <span className="flex items-center gap-1 text-500">
                <Briefcase className="w-3.5 h-3.5" />
                {job.experience}
              </span>
            )}
            {job.education && (
              <span className="text-500">{job.education}</span>
            )}
          </div>

          {/* Description */}
          {job.description && (
            <div>
              <h3 className="text-sm font-medium text-900 mb-2">岗位要求</h3>
              <p className="text-sm text-500 leading-relaxed whitespace-pre-line">
                {job.description}
              </p>
            </div>
          )}

          {/* Skills */}
          {job.skills && job.skills.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-900 mb-2">关键技能</h3>
              <div className="flex flex-wrap gap-2">
                {job.skills.map((skill: string, idx: number) => (
                  <span
                    key={idx}
                    className="px-3 py-1 text-xs bg-layer2 text-700 rounded-input"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Match reasons */}
          {(job.match_reasons?.length > 0 || job.match_risks?.length > 0) && (
            <div>
              <h3 className="text-sm font-medium text-900 mb-2">为什么适合你</h3>
              <div className="space-y-1.5">
                {job.match_reasons?.map((reason: string, idx: number) => (
                  <p key={idx} className="text-sm text-500 flex items-start gap-2">
                    <CheckCircle2 className="w-4 h-4 text-success-600 flex-shrink-0 mt-0.5" />
                    {reason}
                  </p>
                ))}
                {job.match_risks?.map((risk: string, idx: number) => (
                  <p key={idx} className="text-sm text-500 flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-warning-600 flex-shrink-0 mt-0.5" />
                    {risk}
                  </p>
                ))}
              </div>
            </div>
          )}

          {/* AI 申请建议 */}
          <div>
            <h3 className="text-sm font-medium text-900 mb-2 flex items-center gap-1.5">
              <Lightbulb className="w-4 h-4 text-primary-500" />
              AI 申请建议
            </h3>
            {loadingExplanation ? (
              <div className="flex items-center gap-2 text-sm text-primary-500 py-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                AI 正在分析...
              </div>
            ) : aiExplanation ? (
              <div className="space-y-2">
                {aiExplanation.match_reasons?.length > 0 && (
                  <div className="space-y-1">
                    {aiExplanation.match_reasons.map((reason: string, idx: number) => (
                      <div key={idx} className="flex items-start gap-2 text-sm text-500">
                        <CheckCircle2 className="w-3.5 h-3.5 text-success-600 flex-shrink-0 mt-0.5" />
                        <span>{reason}</span>
                      </div>
                    ))}
                  </div>
                )}
                {aiExplanation.match_risks?.length > 0 && (
                  <div className="space-y-1">
                    {aiExplanation.match_risks.map((risk: string, idx: number) => (
                      <div key={idx} className="flex items-start gap-2 text-sm text-500">
                        <AlertTriangle className="w-3.5 h-3.5 text-warning-600 flex-shrink-0 mt-0.5" />
                        <span>{risk}</span>
                      </div>
                    ))}
                  </div>
                )}
                {aiExplanation.resume_tips?.length > 0 && (
                  <div className="pt-2 border-t border-l1">
                    <div className="flex items-center gap-1.5 text-xs font-medium text-primary-700 mb-2">
                      <FileText className="w-3.5 h-3.5" />
                      简历优化建议
                    </div>
                    {aiExplanation.resume_tips.map((tip: any, idx: number) => (
                      <div key={idx} className="text-sm text-500 mb-2 last:mb-0">
                        <span className="text-400">「{tip.original}」</span>
                        <ArrowRight className="w-3 h-3 inline mx-1 text-primary-500" />
                        <span className="text-primary-700">{tip.suggested}</span>
                      </div>
                    ))}
                  </div>
                )}
                {aiExplanation.fallback_message && (
                  <p className="text-sm text-400 italic">{aiExplanation.fallback_message}</p>
                )}
              </div>
            ) : (
              <p className="text-sm text-400">暂无 AI 分析结果</p>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-l1 flex items-center justify-end gap-3">
          <Button onClick={onBookmark} variant="secondary" size="sm">
            <Bookmark className="w-4 h-4" />
            收藏岗位
          </Button>
          <Button onClick={() => { onApply?.(); onClose(); }} variant="primary" size="sm">
            <Send className="w-4 h-4" />
            准备投递
          </Button>
        </div>
      </div>
    </div>
  );
}
