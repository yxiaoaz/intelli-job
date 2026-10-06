'use client';

import { useState, useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import { ChevronDown, FileText, TrendingUp, UserRound, Circle } from 'lucide-react';
import ResumeStatusCard from './ResumeStatusCard';
import IntentDisplay from './IntentDisplay';

interface ContextPillProps {
  sessionId: string;
}

interface ResumeSummary {
  latest_title?: string | null;
  latest_company?: string | null;
  highest_degree?: string | null;
  skills_preview?: string[];
  completeness?: number | null;
}

/**
 * Header context pill — shows resume + intent summary, expands to full details.
 * ui-redesign 决策 5.3：下拉拆为「简历文件 / 画像摘要 / 求职意向」三个独立分区，
 * 面板限高 60vh 可滚动（避免长简历擑破页面）。
 */
export default function ContextPill({ sessionId }: ContextPillProps) {
  const [open, setOpen] = useState(false);
  const [resumeSummary, setResumeSummary] = useState<string | null>(null);
  const [profileSummary, setProfileSummary] = useState<ResumeSummary | null>(null);
  const [intentSummary, setIntentSummary] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click + Escape（修复下拉展开后无法关闭的问题）
  useEffect(() => {
    const handleOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', handleOutside);
    document.addEventListener('click', handleOutside);   // 兑现 headless/自动化环境的点击关闭
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleOutside);
      document.removeEventListener('click', handleOutside);
      document.removeEventListener('keydown', handleKey);
    };
  }, []);

  // Fetch resume summary for pill label
  useEffect(() => {
    const fetchResume = async () => {
      try {
        const token = localStorage.getItem('access_token');
        const res = await fetch('/api/v1/resumes', {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          // API 返回裸数组；只展示默认（使用中）简历，与 agent/匹配链路的
          // active_status 判定保持一致，避免“已解析但 agent 说没简历”的矛盾
          const resumes = Array.isArray(data) ? data : data.resumes || [];
          const active = resumes.find((r: any) => r.is_default) || resumes[0];
          if (!active) return;
          if (active.summary) setProfileSummary(active.summary);
          if (active.is_default) {
            const name = active.filename;
            const status =
              active.status === 'completed' || active.status === 'parsed'
                ? '已解析'
                : '解析中';
            setResumeSummary(`${name} · 默认 · ${status}`);
          } else if (resumes.length > 0) {
            setResumeSummary('简历未设为默认，点击查看');
          }
        }
      } catch {
        // ignore
      }
    };
    fetchResume();
  }, []);

  // Fetch intent summary for pill label
  useEffect(() => {
    const fetchIntent = async () => {
      try {
        const token = localStorage.getItem('access_token');
        const res = await fetch(`/api/v1/chat/sessions/${sessionId}/intent`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          const intent = data.intent;
          if (intent) {
            const roles = intent.target_roles?.slice(0, 2).join('/') || '';
            const locs = intent.locations?.slice(0, 2).join('/') || '';
            if (roles || locs) {
              setIntentSummary([roles, locs].filter(Boolean).join(' · '));
            }
          }
        }
      } catch {
        // ignore
      }
    };
    if (sessionId) fetchIntent();
  }, [sessionId]);

  // Build pill label
  const pillLabel = [resumeSummary, intentSummary].filter(Boolean).join(' | ');
  const hasProfile = !!profileSummary;

  const SectionTitle = ({ icon, label }: { icon: ReactNode; label: string }) => (
    <div className="flex items-center gap-1.5 mb-2">
      <span className="text-400 flex items-center">{icon}</span>
      <span className="text-xs font-medium text-500">{label}</span>
    </div>
  );

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex items-center gap-1.5 h-7 px-2.5 text-xs rounded-btn
                   bg-layer2 border border-l1 text-700
                   hover:bg-hover-neutral hover:border-l2
                   transition-colors duration-base ease-ds"
      >
        <Circle className="w-1.5 h-1.5 fill-current text-success-400 flex-shrink-0" strokeWidth={0} />
        <span className="max-w-[200px] truncate">
          {pillLabel || '上下文'}
        </span>
        <ChevronDown className="w-3 h-3 flex-shrink-0" />
      </button>

      {/* Dropdown panel — 限高 60vh 可滚动（决策 5.3），下拉阴影 lv2（决策 4） */}
      <div
        className={`absolute top-full right-0 mt-2 w-[360px] max-h-[60vh] overflow-y-auto z-50
                    bg-layer1 border border-l1 rounded-menu shadow-lv2
                    transition-opacity duration-base ease-ds
                    ${open ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
      >
        {/* 1) 简历文件 */}
        <div className="p-4 border-b border-l1">
          <SectionTitle icon={<FileText className="w-3.5 h-3.5" strokeWidth={1.5} />} label="简历文件" />
          <ResumeStatusCard
            sessionId={sessionId}
            showSummary={false}
            onUploadSuccess={() => {
              // Refresh pill summary after upload
              window.location.reload(); // simple refresh
            }}
          />
        </div>

        {/* 2) 画像摘要 */}
        <div className="p-4 border-b border-l1">
          <SectionTitle icon={<UserRound className="w-3.5 h-3.5" strokeWidth={1.5} />} label="画像摘要" />
          {hasProfile ? (
            <div className="space-y-1.5 text-xs text-700">
              {(profileSummary?.latest_title || profileSummary?.latest_company) && (
                <p className="truncate">
                  {profileSummary?.latest_title || '—'}
                  {profileSummary?.latest_company ? ` @ ${profileSummary.latest_company}` : ''}
                </p>
              )}
              {profileSummary?.highest_degree && <p>最高学历：{profileSummary.highest_degree}</p>}
              {!!profileSummary?.skills_preview?.length && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {profileSummary.skills_preview.map((skill, idx) => (
                    <span key={idx} className="px-1.5 py-0.5 rounded-input bg-layer2 text-700">{skill}</span>
                  ))}
                </div>
              )}
              {profileSummary?.completeness != null && (
                <p className="text-400 pt-1">完整度 {profileSummary.completeness}%</p>
              )}
            </div>
          ) : (
            <p className="text-xs text-400">暂无解析结果，上传简历后自动生成</p>
          )}
        </div>

        {/* 3）求职意向 */}
        <div className="p-4">
          <SectionTitle icon={<TrendingUp className="w-3.5 h-3.5" strokeWidth={1.5} />} label="求职意向" />
          <IntentDisplay sessionId={sessionId} />
        </div>
      </div>
    </div>
  );
}
