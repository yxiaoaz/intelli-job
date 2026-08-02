'use client';

import { useState, useEffect, useRef } from 'react';
import { ChevronDown, FileText, TrendingUp } from 'lucide-react';
import ResumeStatusCard from './ResumeStatusCard';
import IntentDisplay from './IntentDisplay';

interface ContextPillProps {
  sessionId: string;
}

/**
 * Header context pill — shows resume + intent summary, expands to full details.
 * Replaces the inline ResumeStatusCard + IntentDisplay below the input area.
 */
export default function ContextPill({ sessionId }: ContextPillProps) {
  const [open, setOpen] = useState(false);
  const [resumeSummary, setResumeSummary] = useState<string | null>(null);
  const [intentSummary, setIntentSummary] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
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
          if (data.resumes?.length > 0) {
            const r = data.resumes[0];
            const name = r.parsed_data?.name || r.filename;
            const status = r.status === 'parsed' ? '已解析' : '解析中';
            setResumeSummary(`${name} · ${status}`);
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

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs
                   bg-gray-100 dark:bg-dark-700 border border-gray-200 dark:border-dark-500
                   rounded-full text-gray-600 dark:text-gray-400
                   hover:border-primary-400 dark:hover:border-primary-500 hover:text-primary-600 dark:hover:text-primary-400
                   transition-all duration-150"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" />
        <span className="max-w-[200px] truncate">
          {pillLabel || '上下文'}
        </span>
        <ChevronDown className={`w-3 h-3 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown panel */}
      <div
        className={`absolute top-full right-0 mt-2 w-[340px] z-50
                    bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-600
                    rounded-xl shadow-xl transition-all duration-200 origin-top-right
                    ${open ? 'opacity-100 scale-100 pointer-events-auto' : 'opacity-0 scale-95 pointer-events-none'}`}
      >
        {/* Resume section */}
        <div className="p-4 border-b border-gray-100 dark:border-dark-600">
          <div className="flex items-center gap-2 mb-2">
            <FileText className="w-3.5 h-3.5 text-gray-400" />
            <span className="text-[11px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide">
              简历
            </span>
          </div>
          <ResumeStatusCard
            sessionId={sessionId}
            onUploadSuccess={() => {
              // Refresh pill summary after upload
              window.location.reload(); // simple refresh
            }}
          />
        </div>

        {/* Intent section */}
        <div className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-3.5 h-3.5 text-gray-400" />
            <span className="text-[11px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide">
              求职意向
            </span>
          </div>
          <IntentDisplay sessionId={sessionId} />
        </div>
      </div>
    </div>
  );
}
