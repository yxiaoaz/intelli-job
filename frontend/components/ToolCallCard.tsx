'use client';

import { useState } from 'react';
import { CheckCircle2, ChevronDown, ChevronUp } from 'lucide-react';
import type { ToolCall } from './ChatContext';

interface ToolCallCardProps {
  toolCalls: ToolCall[];
  isCompleted: boolean;
}

/**
 * Tool call progress cards.
 *
 * Mode A (streaming): each tool shown individually with spinner/check
 * Mode B (all done): each card independently collapsible into a one-liner
 *   [check] 已为你筛选岗位  [chevron]
 *   (click to expand details)
 */
export default function ToolCallCard({ toolCalls, isCompleted }: ToolCallCardProps) {
  if (!toolCalls || toolCalls.length === 0) return null;

  const allDone = isCompleted && toolCalls.every((tc) => tc.done);

  return (
    <div className="mb-3 space-y-1.5">
      {toolCalls.map((tc, i) => (
        <SingleToolCard key={`${tc.name}-${i}`} tc={tc} collapsed={allDone} />
      ))}
    </div>
  );
}

/** Individual tool card with optional collapse */
function SingleToolCard({ tc, collapsed }: { tc: ToolCall; collapsed: boolean }) {
  const [expanded, setExpanded] = useState(false);

  // Convert display text to "done" form: "正在搜索匹配岗位" → "已为你搜索匹配岗位"
  const doneText = tc.display
    .replace(/^正在/, '已为你')
    .replace(/^已/, '已为你');

  if (collapsed && !expanded) {
    // Collapsed one-liner
    return (
      <button
        onClick={() => setExpanded(true)}
        className="flex items-center gap-2 text-sm text-emerald-600 dark:text-emerald-400
                   hover:text-emerald-700 dark:hover:text-emerald-300
                   cursor-pointer transition-colors duration-200 group w-full text-left"
      >
        <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
        <span className="flex-1">{doneText}</span>
        <ChevronDown className="w-3.5 h-3.5 opacity-60 group-hover:opacity-100 transition-opacity" />
      </button>
    );
  }

  if (collapsed && expanded) {
    // Expanded: show details with collapse button
    return (
      <div>
        <button
          onClick={() => setExpanded(false)}
          className="flex items-center gap-2 text-sm text-emerald-600 dark:text-emerald-400
                     hover:text-emerald-700 dark:hover:text-emerald-300
                     cursor-pointer transition-colors duration-200 group w-full text-left"
        >
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          <span className="flex-1">{doneText}</span>
          <ChevronUp className="w-3.5 h-3.5 opacity-60 group-hover:opacity-100 transition-opacity" />
        </button>
        <div className="pl-6 mt-1">
          <span className="text-xs text-gray-500 dark:text-gray-400">{tc.display}</span>
        </div>
      </div>
    );
  }

  // Mode A: streaming
  return (
    <div className="flex items-center gap-2 text-sm">
      {tc.done ? (
        <>
          <CheckCircle2 className="w-4 h-4 text-emerald-500 dark:text-emerald-400 flex-shrink-0" />
          <span className="text-emerald-600 dark:text-emerald-400">{doneText}</span>
        </>
      ) : (
        <>
          <ToolSpinner />
          <span className="text-gray-500 dark:text-gray-400 tool-shimmer">
            {tc.display}...
          </span>
        </>
      )}
    </div>
  );
}

/** Small animated spinner icon for executing tools */
function ToolSpinner() {
  return (
    <svg
      className="w-4 h-4 text-primary-500 dark:text-primary-400 animate-spin flex-shrink-0"
      viewBox="0 0 24 24"
      fill="none"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="3"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}
