'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Bot, RefreshCw } from 'lucide-react';
import type { Message } from './ChatContext';
import ToolRunGroup from './ToolCallCard';
import { buttonClasses } from './ui/Button';

interface ChatMessageProps {
  message: Message;
  isCompleted: boolean;
  isLastMessage?: boolean;
  hasJobs?: boolean;
  onAction?: (text: string) => void;
  onRetry: () => void;
}

/**
 * Strip JSON code blocks and inline job JSON from assistant message content.
 * Job data is now delivered via SSE `job_results` event → message.jobs,
 * so we no longer need to parse it from text.
 */
function cleanAssistantText(content: string, isCompleted: boolean): string {
  if (!content) return '';

  if (!isCompleted) {
    // During streaming: aggressively remove any JSON-looking content
    let text = content
      .replace(/```[\s\S]*$/g, '')
      .replace(/```json[\s\S]*$/g, '')
      .replace(/\{[\s\S]*"jobs"[\s\S]*$/g, '')
      .replace(/\{[^{}]*"jobs"[^{}]*\}[^{}]*$/g, '')
      .trim();

    if (text.length < 10 && content.includes('jobs')) return '';
    return text;
  }

  // After completion: remove complete JSON code blocks
  let text = content.replace(/```json\s*[\s\S]*?\s*```/g, '');
  text = text.replace(/\{[\s\S]*?"jobs"\s*:[\s\S]*?\}(?=\s*$|\s*```)/g, '');
  return text.trim();
}

/**
 * ui-redesign 决策 6：AI 回复去卡片化——正文直排（无底色无边框），
 * 工具区 / 结果区 / 正文是消息流内的兄弟块；用户消息保留气泡（primary 底 + menu 圆角）。
 * 组件内零 dark: 分支，深浅主题由 globals.css alias 层翻转（决策 1）。
 */
export default function ChatMessage({ message, isCompleted, isLastMessage = false, hasJobs = false, onAction, onRetry }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';

  // Determine the content to display
  const displayContent = isUser
    ? message.content
    : cleanAssistantText(message.content, isCompleted);

  const markdownComponents = {
    h1: ({ node, ...props }: any) => (
      <h1 className="text-xl font-medium text-900 mb-2" {...props} />
    ),
    h2: ({ node, ...props }: any) => (
      <h2 className="text-lg font-medium text-900 mb-2" {...props} />
    ),
    h3: ({ node, ...props }: any) => (
      <h3 className="text-base font-medium text-900 mb-2" {...props} />
    ),
    ul: ({ node, ...props }: any) => <ul className="list-disc list-outside pl-5 mb-2 space-y-1" {...props} />,
    ol: ({ node, ...props }: any) => <ol className="list-decimal list-outside pl-5 mb-2 space-y-1" {...props} />,
    li: ({ node, ...props }: any) => <li {...props} />,
    strong: ({ node, ...props }: any) => <strong className="font-medium text-900" {...props} />,
    em: ({ node, ...props }: any) => <em className="italic" {...props} />,
    p: ({ node, ...props }: any) => <p className="mb-2 leading-relaxed last:mb-0" {...props} />,
    code: ({ node, inline, className, children, ...props }: any) =>
      inline ? (
        <code className="px-1.5 py-0.5 rounded-input font-mono text-sm bg-layer2" {...props}>
          {children}
        </code>
      ) : (
        <code className="block rounded-input p-3 font-mono text-sm overflow-x-auto my-2 bg-layer2" {...props}>
          {children}
        </code>
      ),
    pre: ({ node, ...props }: any) => (
      <pre className="rounded-input p-3 overflow-x-auto my-2 bg-layer2" {...props} />
    ),
    blockquote: ({ node, ...props }: any) => (
      <blockquote className="border-l-2 border-primary-400 pl-4 italic my-2 text-500" {...props} />
    ),
    a: ({ node, ...props }: any) => (
      <a className="text-primary-600 hover:text-primary-800 underline transition-colors duration-base ease-ds" {...props} />
    ),
  };

  if (isUser) {
    return (
      <div className="flex justify-end animate-fade-in">
        <div className="max-w-[85%] bg-user-bubble text-user-bubble rounded-menu px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words">
          {displayContent}
          <p className="text-xs opacity-60 mt-2">{message.timestamp.toLocaleTimeString()}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start gap-3 animate-fade-in">
      {/* Bot avatar — 去渐变（决策 4：全站无彩色渐变），中性底 + 主蓝图标 */}
      <div className="w-8 h-8 rounded-full bg-layer2 border border-l1 flex items-center justify-center flex-shrink-0">
        <Bot className="w-4 h-4 text-primary-600" strokeWidth={1.5} />
      </div>

      {/* 消息流：工具区 / 正文 / 元信息 为兄弟块，正文无卡片包裹 */}
      <div className="flex-1 min-w-0 space-y-3">
        {isAssistant && message.toolCalls && message.toolCalls.length > 0 && (
          <ToolRunGroup toolCalls={message.toolCalls} />
        )}

        {displayContent && (
          <div className="text-sm text-700 max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {displayContent}
            </ReactMarkdown>
          </div>
        )}

        <div className="flex items-center gap-2">
          <p className="text-xs text-400">
            {message.timestamp.toLocaleTimeString()}
          </p>
          {isAssistant && message.isError && (
            <button
              onClick={onRetry}
              className="flex items-center gap-1 text-xs text-primary-600 hover:text-primary-800 transition-colors duration-base ease-ds"
            >
              <RefreshCw className="w-3 h-3" />
              重试
            </button>
          )}
        </div>

        {/* CTA buttons — shown after last assistant message with job results */}
        {isAssistant && isCompleted && isLastMessage && hasJobs && onAction && (
          <div className="flex flex-wrap gap-2 pt-1">
            {[
              '查看岗位详情',
              '帮我优化简历',
              '准备面试问题',
              '调整搜索条件',
            ].map((label) => (
              <button
                key={label}
                onClick={() => onAction(label)}
                className={buttonClasses('secondary', 'sm')}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
