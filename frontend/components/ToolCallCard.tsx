'use client';

/**
 * ui-redesign Phase 3：工具调用卡片（决策 12-16）。
 *
 * 三层结构：
 *   ToolRunGroup  卡片壳（bg-layer1 + border-l1 + menu 圆角）
 *     ├─ ToolRow      单行 disclosure：16px 恒宽图标槽 + 标题 + 摘要 + chevron
 *     │    └─ ToolDetails  IN/OUT 双段（有内容才可展开）
 *     └─ ToolGroupRow 连续同类调用合并行（N 步 · 耗时求和）
 *
 * 四态样式（决策 13）：running 蓝点闪烁 + 行底扫光 / ok 工具线性图标 /
 * error 红实心点 / stopped 琥珀点。行高恒定，展开为组件 local useState。
 *
 * 本组件直接消费 Phase 1 新语义 token（bg-layer1/border-l1/rounded-menu/
 * success|warning|danger/primary-*），不写任何 dark: 分支或旧 primary/accent 类。
 */

import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { ToolCall } from './ChatContext';
import { getToolView, runningLabel, doneLabel, type ToolView } from './tool-views/registry';

const IN_TRUNCATE_AT = 300;
const OUT_HEAD_LINES = 4;
const OUT_TAIL_LINES = 4;

function formatDuration(ms?: number): string {
  if (ms == null) return '';
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

// ── ToolRow ───────────────────────────────────────────

interface ToolRowProps {
  tc: ToolCall;
  view: ToolView;
}

function StatusDot({ color }: { color: string }) {
  return <span className={`w-2 h-2 rounded-full flex-shrink-0 ${color}`} />;
}

function ToolRow({ tc, view }: ToolRowProps) {
  const [expanded, setExpanded] = useState(false);

  const isRunning = tc.status === 'running';
  const isError = tc.status === 'error';
  const isStopped = tc.status === 'stopped';

  const label = isRunning ? runningLabel(view) : isStopped ? '已停止生成' : doneLabel(view);
  const summary = isRunning
    ? view.summarizeArgs?.(tc.args) || ''
    : isStopped
      ? '结果已保留'
      : tc.resultSummary || '';

  const hasDetail = !isRunning && !isStopped && (!!tc.args || (!!tc.resultSummary && !!tc.resultRaw));

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => hasDetail && setExpanded((v) => !v)}
        aria-expanded={hasDetail ? expanded : undefined}
        className={`flex items-center gap-2 w-full text-left px-3 py-[9px] leading-[24px] text-sm
                   ${hasDetail ? 'cursor-pointer' : 'cursor-default'}`}
      >
        {/* 16px 恒宽图标槽，四态共用同一槽位，行高/宽度恒定不跳动 */}
        <span className="w-4 h-4 flex items-center justify-center flex-shrink-0">
          {isRunning ? (
            <StatusDot color="bg-primary-500 animate-pulse" />
          ) : isError ? (
            <StatusDot color="bg-danger-600" />
          ) : isStopped ? (
            <StatusDot color="bg-warning-600" />
          ) : (
            <span className="text-700">{view.icon}</span>
          )}
        </span>

        <span
          className={`flex-shrink-0 ${isError ? 'text-danger-600' : isStopped ? 'text-warning-600' : 'text-900'}`}
        >
          {label}
        </span>

        {summary && (
          <>
            <span className="text-400 flex-shrink-0">·</span>
            <span
              className={`flex-1 min-w-0 truncate ${isError ? 'text-danger-600' : 'text-500'}`}
            >
              {summary}
            </span>
          </>
        )}
        {!summary && <span className="flex-1" />}

        {hasDetail && (
          <span className="text-400 flex-shrink-0">
            {expanded ? (
              <ChevronDown className="w-3.5 h-3.5" strokeWidth={1.5} />
            ) : (
              <ChevronRight className="w-3.5 h-3.5" strokeWidth={1.5} />
            )}
          </span>
        )}
      </button>

      {/* running 行底 2px 扫光（决策 13；动画本体在 globals.css 的 prefers-reduced-motion 分支内） */}
      {isRunning && <span className="tool-shimmer absolute inset-0 pointer-events-none" aria-hidden />}

      {isError && (
        <div className="pl-8 pr-3 pb-1">
          <span className="text-xs text-danger-600">重试</span>
        </div>
      )}

      {hasDetail && expanded && (
        <ToolDetails view={view} args={tc.args} resultSummary={tc.resultSummary} resultRaw={tc.resultRaw} />
      )}
    </div>
  );
}

// ── ToolDetails（决策 15：IN/OUT 双段，各 max-height 150px 独立滚动） ──

interface ToolDetailsProps {
  view: ToolView;
  args: unknown;
  resultSummary?: string;
  resultRaw?: string;
}

function ToolDetails({ view, args, resultSummary, resultRaw }: ToolDetailsProps) {
  const argsPretty = (() => {
    if (args == null) return '';
    try {
      const s = typeof args === 'string' ? args : JSON.stringify(args, null, 2);
      return s.length > IN_TRUNCATE_AT ? `${s.slice(0, IN_TRUNCATE_AT)}…` : s;
    } catch {
      return String(args).slice(0, IN_TRUNCATE_AT);
    }
  })();

  const renderOut = view.renderDetail?.(args, resultRaw || '');

  return (
    <div className="mx-3 mb-2 bg-layer2 border border-l1 rounded-menu p-2.5 space-y-2 text-xs">
      {argsPretty && (
        <div>
          <p className="text-400 mb-1">输入</p>
          <pre className="font-mono text-700 max-h-[150px] overflow-auto whitespace-pre-wrap break-all">
            {argsPretty}
          </pre>
        </div>
      )}
      <div>
        <p className="text-400 mb-1">输出</p>
        {renderOut ? (
          <div className="max-h-[150px] overflow-auto">{renderOut}</div>
        ) : (
          <pre className="font-mono text-700 max-h-[150px] overflow-auto whitespace-pre-wrap break-all">
            {headAndTail(resultRaw || resultSummary || '')}
          </pre>
        )}
      </div>
    </div>
  );
}

/** 决策 15：输出段原始结果前 8 行 head + `… +N lines` + tail */
function headAndTail(text: string): string {
  const lines = text.split('\n');
  if (lines.length <= OUT_HEAD_LINES + OUT_TAIL_LINES) return text;
  const head = lines.slice(0, OUT_HEAD_LINES);
  const tail = lines.slice(-OUT_TAIL_LINES);
  const skipped = lines.length - head.length - tail.length;
  return [...head, `… +${skipped} lines`, ...tail].join('\n');
}

// ── ToolGroupRow（决策 14：分组合并） ──

interface ToolGroupRowProps {
  tcs: ToolCall[];
}

function ToolGroupRow({ tcs }: ToolGroupRowProps) {
  const [expanded, setExpanded] = useState(false);
  const totalMs = tcs.reduce((sum, tc) => sum + (tc.durationMs || 0), 0);
  // 合并行标题：组内只有一种动作时用它的完成态文案，
  // 多种动作（读/写记忆文件、查画像）合并时回退到决策 14 的聚合文案
  const firstTitle = doneLabel(getToolView(tcs[0].name));
  const uniform = tcs.every((tc) => doneLabel(getToolView(tc.name)) === firstTitle);
  const groupTitle = uniform ? firstTitle : '已查阅记忆与画像';

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="flex items-center gap-2 w-full text-left px-3 py-[9px] leading-[24px] text-sm cursor-pointer"
      >
        <span className="w-4 h-4 flex items-center justify-center flex-shrink-0 text-700">
          {getToolView(tcs[0].name).icon}
        </span>
        <span className="text-900 flex-shrink-0">{groupTitle}</span>
        <span className="text-400 flex-shrink-0">·</span>
        <span className="text-500 flex-1 min-w-0 truncate">
          {tcs.length} 步{totalMs ? ` · ${formatDuration(totalMs)}` : ''}
        </span>
        <span className="text-400 flex-shrink-0">
          {expanded ? (
            <ChevronDown className="w-3.5 h-3.5" strokeWidth={1.5} />
          ) : (
            <ChevronRight className="w-3.5 h-3.5" strokeWidth={1.5} />
          )}
        </span>
      </button>

      {expanded && (
        <div className="ml-[22px] border-l border-l1">
          {tcs.map((tc) => {
            const view = getToolView(tc.name);
            return (
              <div
                key={tc.id}
                className="flex items-center gap-2 px-3 py-[9px] leading-[24px] text-xs text-500"
              >
                <span className="flex-shrink-0">{view.icon}</span>
                <span className="text-700">{doneLabel(view)}</span>
                <span className="text-400">·</span>
                <span className="truncate">{tc.resultSummary || view.summarizeArgs?.(tc.args) || ''}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── 合并算法（决策 14） ──

type RenderUnit = { kind: 'single'; tc: ToolCall } | { kind: 'group'; tcs: ToolCall[] };

function buildRenderUnits(toolCalls: ToolCall[]): RenderUnit[] {
  const units: RenderUnit[] = [];
  let buffer: ToolCall[] = [];

  const flush = () => {
    if (buffer.length === 0) return;
    if (buffer.length === 1) units.push({ kind: 'single', tc: buffer[0] });
    else units.push({ kind: 'group', tcs: buffer });
    buffer = [];
  };

  for (const tc of toolCalls) {
    const view = getToolView(tc.name);
    // running 不合并、error 不合并、groupable:false（如 search_jobs）不合并
    const canGroup = view.groupable && tc.status === 'ok';
    if (canGroup) {
      buffer.push(tc);
    } else {
      flush();
      units.push({ kind: 'single', tc });
    }
  }
  flush();
  return units;
}

// ── ToolRunGroup（顶层导出，替换旧 ToolCallCard） ──

interface ToolRunGroupProps {
  toolCalls: ToolCall[];
}

export default function ToolRunGroup({ toolCalls }: ToolRunGroupProps) {
  if (!toolCalls || toolCalls.length === 0) return null;

  const units = buildRenderUnits(toolCalls);

  return (
    <div className="mb-3 bg-layer1 border border-l1 rounded-menu overflow-hidden divide-y divide-l1">
      {units.map((unit, i) =>
        unit.kind === 'group' ? (
          <ToolGroupRow key={`g-${i}`} tcs={unit.tcs} />
        ) : (
          <ToolRow key={unit.tc.id} tc={unit.tc} view={getToolView(unit.tc.name)} />
        )
      )}
    </div>
  );
}
