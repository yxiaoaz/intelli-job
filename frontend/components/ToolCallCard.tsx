'use client';

import { useState } from 'react';
import { CheckCircle2, ChevronDown, ChevronUp } from 'lucide-react';
import type { ToolCall } from './ChatContext';

interface ToolCallCardProps {
  toolCalls: ToolCall[];
  isCompleted: boolean;
}

/**
 * Tool call progress cards — inspired by open-webui's ToolCallDisplay + ConsecutiveDetailsGroup.
 *
 * Mode A (streaming, some tools still running): each tool shown individually
 *   [spinner + shimmer] 正在搜索匹配岗位...
 *   [green check] 已查阅用户偏好
 *
 * Mode B (all done after completion): collapsed into a one-line summary
 *   ✅ 已使用 3 个工具    [chevron]
 *   (click to expand)
 */
export default function ToolCallCard({ toolCalls, isCompleted }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false);

  if (!toolCalls || toolCalls.length === 0) return null;

  const allDone = toolCalls.every((tc) => tc.done);
  const shouldCollapse = isCompleted && allDone;

  // ── Mode B: collapsed summary ──
  if (shouldCollapse) {
    const uniqueNames = Array.from(new Set(toolCalls.map((tc) => tc.name)));
    return (
      <div className="mb-3">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-2 text-sm text-emerald-600 dark:text-emerald-400
                     hover:text-emerald-700 dark:hover:text-emerald-300
                     cursor-pointer transition-colors duration-200 group"
        >
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          <span>
            已使用 {uniqueNames.length} 个工具
            <span className="text-gray-400 dark:text-gray-500 ml-1.5 text-xs">
              ({uniqueNames.join(', ')})
            </span>
          </span>
          {expanded ? (
            <ChevronUp className="w-3.5 h-3.5 opacity-60 group-hover:opacity-100 transition-opacity" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 opacity-60 group-hover:opacity-100 transition-opacity" />
          )}
        </button>

        {/* Expanded details */}
        <div
          className={`overflow-hidden transition-all duration-300 ease-in-out ${
            expanded ? 'max-h-96 opacity-100 mt-2' : 'max-h-0 opacity-0'
          }`}
        >
          <div className="space-y-1 pl-1">
            {toolCalls.map((tc, i) => (
              <div
                key={`${tc.name}-${i}`}
                className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400"
              >
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 dark:text-emerald-400 flex-shrink-0" />
                <span>{tc.display}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ── Mode A: streaming, show each tool individually ──
  return (
    <div className="mb-3 space-y-1.5">
      {toolCalls.map((tc, i) => (
        <div
          key={`${tc.name}-${i}`}
          className="flex items-center gap-2 text-sm"
        >
          {tc.done ? (
            <>
              <CheckCircle2 className="w-4 h-4 text-emerald-500 dark:text-emerald-400 flex-shrink-0" />
              <span className="text-emerald-600 dark:text-emerald-400">
                {tc.display.replace('正在', '已完成')}
              </span>
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
      ))}
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
