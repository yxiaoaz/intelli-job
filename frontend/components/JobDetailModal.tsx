'use client';

import { useEffect } from 'react';
import { X, DollarSign, Briefcase, Bookmark, Send } from 'lucide-react';

interface JobDetailModalProps {
  job: any | null;
  onClose: () => void;
  onApply?: () => void;
  onBookmark?: () => void;
}

export default function JobDetailModal({ job, onClose, onApply, onBookmark }: JobDetailModalProps) {
  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

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
      <div className="bg-white dark:bg-dark-800 rounded-2xl w-[520px] max-h-[80vh] shadow-2xl flex flex-col animate-fade-in">
        {/* Header */}
        <div className="px-6 pt-5 pb-4 border-b border-gray-100 dark:border-dark-600 flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-bold text-gray-900 dark:text-white truncate">{job.title}</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              {job.company} · {job.location || '未指定'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-600 hover:text-gray-600 transition-colors flex-shrink-0 ml-3"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {/* Salary + meta */}
          <div className="flex items-center gap-4 text-sm">
            <span className="flex items-center gap-1.5 text-green-600 dark:text-green-400 font-semibold">
              <DollarSign className="w-4 h-4" />
              {formatSalary()}
            </span>
            {job.experience && (
              <span className="flex items-center gap-1 text-gray-500 dark:text-gray-400">
                <Briefcase className="w-3.5 h-3.5" />
                {job.experience}
              </span>
            )}
            {job.education && (
              <span className="text-gray-500 dark:text-gray-400">{job.education}</span>
            )}
          </div>

          {/* Description */}
          {job.description && (
            <div>
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">岗位要求</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed whitespace-pre-line">
                {job.description}
              </p>
            </div>
          )}

          {/* Skills */}
          {job.skills && job.skills.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">关键技能</h3>
              <div className="flex flex-wrap gap-2">
                {job.skills.map((skill: string, idx: number) => (
                  <span
                    key={idx}
                    className="px-3 py-1 text-xs bg-gray-100 dark:bg-dark-600 text-gray-600 dark:text-gray-400 rounded-md"
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
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">为什么适合你</h3>
              <div className="space-y-1.5">
                {job.match_reasons?.map((reason: string, idx: number) => (
                  <p key={idx} className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2">
                    <span className="text-emerald-500 mt-0.5">✓</span>
                    {reason}
                  </p>
                ))}
                {job.match_risks?.map((risk: string, idx: number) => (
                  <p key={idx} className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2">
                    <span className="text-amber-500 mt-0.5">⚠</span>
                    {risk}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-100 dark:border-dark-600 flex items-center justify-end gap-3">
          <button
            onClick={onBookmark}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium
                       bg-gray-100 dark:bg-dark-600 text-gray-700 dark:text-gray-300
                       rounded-lg hover:bg-gray-200 dark:hover:bg-dark-500 transition-colors"
          >
            <Bookmark className="w-4 h-4" />
            收藏岗位
          </button>
          <button
            onClick={() => { onApply?.(); onClose(); }}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium
                       bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            <Send className="w-4 h-4" />
            准备投递
          </button>
        </div>
      </div>
    </div>
  );
}
