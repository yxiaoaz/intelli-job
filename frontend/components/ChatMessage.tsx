'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Bot, User, RefreshCw } from 'lucide-react';
import type { Message } from './ChatContext';
import ToolCallCard from './ToolCallCard';

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

export default function ChatMessage({ message, isCompleted, isLastMessage = false, hasJobs = false, onAction, onRetry }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';

  // Determine the content to display
  const displayContent = isUser
    ? message.content
    : cleanAssistantText(message.content, isCompleted);

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in`}>
      <div
        className={`max-w-[85%] rounded-2xl p-5 ${
          isUser
            ? 'bg-gradient-to-r from-primary-600 to-primary-500 text-white shadow-lg'
            : 'glass shadow-md border border-primary-200/50 dark:border-primary-700/50 text-gray-900 dark:text-gray-100'
        }`}
      >
        <div className="flex items-start gap-3">
          {/* Bot avatar (assistant only) */}
          {isAssistant && (
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center flex-shrink-0 shadow-md">
              <Bot className="w-5 h-5 text-white" />
            </div>
          )}

          <div className="flex-1 min-w-0">
            {/* Tool call cards (assistant only) */}
            {isAssistant && message.toolCalls && message.toolCalls.length > 0 && (
              <ToolCallCard toolCalls={message.toolCalls} isCompleted={isCompleted} />
            )}

            {/* Message content */}
            {displayContent && (
              <div className="prose prose-sm dark:prose-invert max-w-none mb-4">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h1: ({ node, ...props }) => (
                      <h1 className={`text-xl font-bold mb-2 ${isUser ? 'text-white' : 'text-gray-900 dark:text-white'}`} {...props} />
                    ),
                    h2: ({ node, ...props }) => (
                      <h2 className={`text-lg font-bold mb-2 ${isUser ? 'text-white' : 'text-gray-900 dark:text-white'}`} {...props} />
                    ),
                    h3: ({ node, ...props }) => (
                      <h3 className={`text-base font-bold mb-2 ${isUser ? 'text-white' : 'text-gray-900 dark:text-white'}`} {...props} />
                    ),
                    ul: ({ node, ...props }) => <ul className="list-disc list-inside mb-2 space-y-1" {...props} />,
                    ol: ({ node, ...props }) => <ol className="list-decimal list-inside mb-2 space-y-1" {...props} />,
                    li: ({ node, ...props }) => (
                      <li className={isUser ? 'text-white/90' : 'text-gray-700 dark:text-gray-300'} {...props} />
                    ),
                    strong: ({ node, ...props }) => (
                      <strong className={`font-bold ${isUser ? 'text-white' : 'text-gray-900 dark:text-white'}`} {...props} />
                    ),
                    em: ({ node, ...props }) => (
                      <em className={`italic ${isUser ? 'text-white/90' : 'text-gray-700 dark:text-gray-300'}`} {...props} />
                    ),
                    p: ({ node, ...props }) => (
                      <p className={`mb-2 leading-relaxed ${isUser ? 'text-white/95' : 'text-gray-700 dark:text-gray-300'}`} {...props} />
                    ),
                    code: ({ node, inline, className, children, ...props }: any) =>
                      inline ? (
                        <code className={`px-1.5 py-0.5 rounded text-sm font-mono ${isUser ? 'bg-white/20 text-white' : 'bg-gray-100 dark:bg-dark-600 text-gray-800 dark:text-gray-200'}`} {...props}>
                          {children}
                        </code>
                      ) : (
                        <code className={`block rounded-lg p-3 text-sm font-mono overflow-x-auto my-2 ${isUser ? 'bg-white/20 text-white' : 'bg-gray-100 dark:bg-dark-600 text-gray-800 dark:text-gray-200'}`} {...props}>
                          {children}
                        </code>
                      ),
                    pre: ({ node, ...props }) => (
                      <pre className={`rounded-lg p-3 overflow-x-auto my-2 ${isUser ? 'bg-white/20' : 'bg-gray-100 dark:bg-dark-600'}`} {...props} />
                    ),
                    blockquote: ({ node, ...props }) => (
                      <blockquote className={`border-l-4 pl-4 italic my-2 ${isUser ? 'border-white/50 text-white/80' : 'border-primary-400 text-gray-600 dark:text-gray-400'}`} {...props} />
                    ),
                    a: ({ node, ...props }) => (
                      <a className={`${isUser ? 'text-white underline hover:text-white/80' : 'text-primary-600 dark:text-primary-400 hover:underline'}`} {...props} />
                    ),
                  }}
                >
                  {displayContent}
                </ReactMarkdown>
              </div>
            )}

            {/* Timestamp + retry */}
            <div className="flex items-center gap-2 mt-3">
              <p className={`text-xs ${isUser ? 'text-primary-100' : 'text-gray-500 dark:text-gray-400'}`}>
                {message.timestamp.toLocaleTimeString()}
              </p>
              {isAssistant && message.isError && (
                <button
                  onClick={onRetry}
                  className="flex items-center gap-1 text-xs text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 transition-colors"
                >
                  <RefreshCw className="w-3 h-3" />
                  重试
                </button>
              )}
            </div>

            {/* CTA buttons — shown after last assistant message with job results */}
            {isAssistant && isCompleted && isLastMessage && hasJobs && onAction && (
              <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-gray-100 dark:border-dark-600">
                {[
                  '查看岗位详情',
                  '帮我优化简历',
                  '准备面试问题',
                  '调整搜索条件',
                ].map((label) => (
                  <button
                    key={label}
                    onClick={() => onAction(label)}
                    className="px-4 py-2 text-xs font-medium rounded-full
                               bg-gray-100 dark:bg-dark-600 border border-gray-200 dark:border-dark-500
                               text-gray-700 dark:text-gray-300
                               hover:bg-primary-50 dark:hover:bg-primary-900/20
                               hover:border-primary-300 dark:hover:border-primary-600
                               hover:text-primary-700 dark:hover:text-primary-400
                               transition-all duration-150"
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* User avatar */}
          {isUser && (
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-400 to-primary-500 flex items-center justify-center flex-shrink-0 shadow-md">
              <User className="w-5 h-5 text-white" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
