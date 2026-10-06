'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useChat } from '@/components/ChatContext';
import { ChatSidebar } from '@/components/ChatSidebar';
import ContextPill from '@/components/ContextPill';
import ThinkingIndicator from '@/components/ThinkingIndicator';
import ChatMessage from '@/components/ChatMessage';
import JobResultsSection from '@/components/JobResultsSection';
import Button from '@/components/ui/Button';
import { Send, Bot, Square, Briefcase, PencilRuler, Lightbulb, Sparkle } from 'lucide-react';

export default function ChatPage() {
  const router = useRouter();
  const { 
    sessions, sessionId, messages, loading, isInitialized, isThinking,
    sendMessage, cancelStream, newChat, switchSession, ensureSession, completedMessages, markMessageComplete,
    pendingDraft, clearPendingDraft
  } = useChat();
  const [input, setInput] = useState('');
  // ✅ ui-redesign 决策 13：当前正在流式输出的消息（最后一条）如果已经有工具调用，
  // 工具区就是实时反馈本身，ThinkingIndicator 需要隐藏，避免双重反馈
  const lastStreamingMessageHasTools =
    loading && messages.length > 0 && (messages[messages.length - 1]?.toolCalls?.length ?? 0) > 0;
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [isUserAtBottom, setIsUserAtBottom] = useState(true);
  
  // ✅ 防止 React Strict Mode 导致 useEffect 重复执行
  const isMountedRef = useRef<boolean>(false);

  // Check authentication and ensure session exists on mount
  useEffect(() => {
    // ✅ 防止 React Strict Mode 导致重复执行
    if (isMountedRef.current) return;
    isMountedRef.current = true;
    
    // ✅ 不再在这里检查 token，axios 拦截器会统一处理 401
    // 直接确保 session 存在，如果 token 无效，拦截器会自动跳转登录
    try {
      ensureSession();
    } catch (err) {
      console.error('Failed to ensure session:', err);
      // 如果 ensureSession 失败（可能是 401），清除状态
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('chat_session_id');
      // ✅ 不再调用 router.push，让 axios 拦截器处理
    }
  }, [router, ensureSession]);

  // ✅ 会话切换/新建时清空输入草稿，避免残留内容拼进新会话被一起发出
  useEffect(() => {
    setInput('');
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }
  }, [sessionId]);

  // ✅ 发送失败后恢复草稿到输入框
  useEffect(() => {
    if (pendingDraft) {
      setInput(pendingDraft);
      clearPendingDraft();
      inputRef.current?.focus();
    }
  }, [pendingDraft, clearPendingDraft]);

  // Auto scroll to bottom - only when user is at bottom
  useEffect(() => {
    if (isUserAtBottom && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isUserAtBottom]);

  // Track user scroll position
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    
    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      // 判断是否在底部(留 50px 容差)
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
      setIsUserAtBottom(isAtBottom);
    };
    
    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
  }, []);

  // Auto-focus input
  useEffect(() => {
    if (!loading && inputRef.current) {
      inputRef.current.focus();
    }
  }, [loading, messages]);

  const handleSend = () => {
    if (!input.trim() || loading) return;
    sendMessage(input);
    setInput('');
    // Reset textarea height
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewChat = () => {
    newChat();
  };

  // Note: parseJobsFromMessage and extractCleanText have been moved to
  // ChatMessage.tsx component. Job data now arrives via SSE job_results event.

  return (
    <div className="min-h-screen bg-base flex animate-fade-in">
      {/* Sidebar */}
      <ChatSidebar />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header — 中性表面 + 1px 边框（glass 已在 Phase 4.4 降级替换） */}
        <header className="bg-layer1 border-b border-l1 shadow-lv1 sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 py-3 flex justify-between items-center">
            <h1 className="text-lg font-medium gradient-text">Intelli-Job</h1>
            <nav className="flex items-center gap-4">
              <button
                onClick={() => router.push('/dashboard')}
                className="text-sm text-700 hover:text-primary-600 transition-colors"
              >
                职位
              </button>
              <button
                onClick={() => router.push('/resumes')}
                className="text-sm text-700 hover:text-primary-600 transition-colors"
              >
                简历
              </button>
              <button
                onClick={() => router.push('/chat')}
                className="text-sm text-primary-600 font-medium"
              >
                AI助手
              </button>
              {sessionId && <ContextPill sessionId={sessionId} />}
            </nav>
          </div>
        </header>

        {/* Chat Area — ui-redesign 决策 6：消息列与输入框同轴 748px 内容轴 */}
        <main className="flex-1 w-full px-[var(--ij-chat-side-clearance)] py-8 flex flex-col">
        <div className="w-full max-w-[var(--ij-chat-max-width)] mx-auto flex-1 flex flex-col min-h-0">
        {/* Messages */}
        <div 
          ref={messagesContainerRef}
          className="flex-1 space-y-4 mb-4 overflow-y-auto"
        >
          {!isInitialized && messages.length > 0 ? (
            <div className="text-center py-12">
              <div className="loading-dots mx-auto">
                <span></span><span></span><span></span>
              </div>
            </div>
          ) : messages.length === 0 ? (
            <div className="text-center py-12 animate-fade-in">
              <Sparkle className="w-14 h-14 text-400 mx-auto mb-4" strokeWidth={1.5} />
              <p className="text-900 text-lg font-medium mb-1">你好！我是你的 AI 求职助手</p>
              <p className="text-500 text-sm mb-6">
                帮你搜索岗位、分析简历、规划求职方向
              </p>
              <div className="space-y-3 text-sm text-700">
                <p className="font-medium">试试这样说：</p>
                <button
                  onClick={() => setInput('帮我找北京的产品经理工作')}
                  className="flex w-full items-center gap-2 text-left px-4 py-3 bg-layer1 rounded-menu border border-l1 hover:bg-hover-neutral transition-colors duration-base ease-ds"
                >
                  <Briefcase className="w-4 h-4 flex-shrink-0 text-primary-500" strokeWidth={1.5} />
                  “帮我找北京的产品经理工作”
                </button>
                <button
                  onClick={() => setInput('如何优化我的简历？')}
                  className="flex w-full items-center gap-2 text-left px-4 py-3 bg-layer1 rounded-menu border border-l1 hover:bg-hover-neutral transition-colors duration-base ease-ds"
                >
                  <PencilRuler className="w-4 h-4 flex-shrink-0 text-primary-500" strokeWidth={1.5} />
                  “如何优化我的简历？”
                </button>
                <button
                  onClick={() => setInput('互联网行业前景如何？')}
                  className="flex w-full items-center gap-2 text-left px-4 py-3 bg-layer1 rounded-menu border border-l1 hover:bg-hover-neutral transition-colors duration-base ease-ds"
                >
                  <Lightbulb className="w-4 h-4 flex-shrink-0 text-primary-500" strokeWidth={1.5} />
                  “互联网行业前景如何？”
                </button>
              </div>
            </div>
          ) : (
            (() => {
              // Find last assistant message index for CTA
              const lastAssistantIdx = messages.map((m, i) => m.role === 'assistant' ? i : -1).filter(i => i >= 0).pop() ?? -1;

              return messages.map((message, msgIdx) => {
              const jobs = message.jobs ?? [];
              const isCompleted = completedMessages.has(message.id);
              const shouldShowJobs = message.role === 'assistant'
                && jobs.length > 0
                && isCompleted;

              return (
                <div key={message.id} className="space-y-3">
                  {/* Message bubble */}
                  <ChatMessage
                    message={message}
                    isCompleted={isCompleted}
                    isLastMessage={msgIdx === lastAssistantIdx}
                    hasJobs={jobs.length > 0}
                    onAction={(text) => sendMessage(text)}
                    onRetry={() => {
                      const msgIndex = messages.findIndex(m => m.id === message.id);
                      const prevUserMsg = messages.slice(0, msgIndex).reverse().find(m => m.role === 'user');
                      if (prevUserMsg) sendMessage(prevUserMsg.content);
                    }}
                  />

                  {/* Job results — outside bubble, full width, aligned with bot avatar */}
                  {shouldShowJobs && (
                    <div className="ml-11">
                      <JobResultsSection
                        jobs={jobs}
                        onQuickAction={(actionText) => sendMessage(actionText)}
                      />
                    </div>
                  )}
                </div>
              );
            });
          })()
          )}

          {/* Loading indicator — ui-redesign 决策 13：ThinkingIndicator 仅表示模型推理中，
              工具区（当前流式消息的 toolCalls）一旦出现就互斥隐藏，避免双反馈 */}
          {loading && isThinking && !lastStreamingMessageHasTools && (
            <div className="flex justify-start animate-fade-in">
              <ThinkingIndicator />
            </div>
          )}

          {loading && !isThinking && (
            <div className="flex justify-start gap-3 animate-fade-in">
              <div className="w-8 h-8 rounded-full bg-layer2 border border-l1 flex items-center justify-center flex-shrink-0">
                <Bot className="w-4 h-4 text-primary-600" strokeWidth={1.5} />
              </div>
              <div className="flex items-center pt-1.5">
                <div className="loading-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="space-y-3">
          {/* Chat Input */}
          <div className="bg-layer1 rounded-menu shadow-lv1 p-4 border border-l1">
          <div className="flex gap-2 items-end">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                // Auto-resize
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
              }}
              onKeyDown={handleKeyDown}
              placeholder="输入消息...（Shift+Enter 换行）"
              disabled={loading}
              rows={1}
              className="flex-1 px-4 py-3 rounded-input border border-l2 bg-base text-900
                         focus:outline-none focus:ring-2 focus:ring-primary-200 focus:border-transparent disabled:opacity-50
                         transition-colors duration-base ease-ds
                         resize-none overflow-y-auto"
            />
            {loading ? (
              <Button onClick={cancelStream} variant="secondary" className="w-9 h-9 px-0 text-danger-600 hover:text-danger-800" title="停止生成">
                <Square className="w-5 h-5" />
              </Button>
            ) : (
              <Button onClick={handleSend} disabled={!input.trim()} variant="primary" className="w-9 h-9 px-0" title="发送">
                <Send className="w-5 h-5" />
              </Button>
            )}
          </div>
          <p className="text-xs text-500 mt-2 text-center">
            AI助手可能会生成不准确的信息，请谨慎参考
          </p>
        </div>
        </div>
        </div>
        </main>
      </div>
    </div>
  );
}
