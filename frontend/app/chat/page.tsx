'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useChat } from '@/components/ChatContext';
import { ChatSidebar } from '@/components/ChatSidebar';
import ContextPill from '@/components/ContextPill';
import ThinkingIndicator from '@/components/ThinkingIndicator';
import ChatMessage from '@/components/ChatMessage';
import JobResultsSection from '@/components/JobResultsSection';
import { Send, Bot, Square } from 'lucide-react';

export default function ChatPage() {
  const router = useRouter();
  const { 
    sessions, sessionId, messages, loading, isInitialized, isThinking,
    sendMessage, cancelStream, newChat, switchSession, ensureSession, completedMessages, markMessageComplete
  } = useChat();
  const [input, setInput] = useState('');
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
    <div className="min-h-screen bg-gradient-to-br from-dark-50 via-white to-primary-50 dark:from-dark-900 dark:via-dark-800 dark:to-dark-900 flex animate-fade-in">
      {/* Sidebar */}
      <ChatSidebar />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header - 玻璃态 */}
        <header className="glass shadow-md sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 py-3 flex justify-between items-center">
            <h1 className="text-xl font-bold gradient-text font-display">Intelli-Job</h1>
            <nav className="flex items-center gap-4">
              <button
                onClick={() => router.push('/dashboard')}
                className="text-sm text-gray-700 dark:text-gray-300 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
              >
                职位
              </button>
              <button
                onClick={() => router.push('/resumes')}
                className="text-sm text-gray-700 dark:text-gray-300 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
              >
                简历
              </button>
              <button
                onClick={() => router.push('/chat')}
                className="text-sm text-primary-600 dark:text-primary-400 font-semibold"
              >
                AI助手
              </button>
              {sessionId && <ContextPill sessionId={sessionId} />}
            </nav>
          </div>
        </header>

        {/* Chat Area */}
        <main className="flex-1 max-w-4xl mx-auto w-full px-4 py-8 flex flex-col">
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
              <div className="text-primary-400 text-7xl mb-4 animate-pulse-slow">🤖</div>
              <p className="text-gray-700 dark:text-gray-300 text-xl font-semibold mb-1">你好！我是你的 AI 求职助手</p>
              <p className="text-gray-600 dark:text-gray-400 text-sm mb-6">
                帮你搜索岗位、分析简历、规划求职方向
              </p>
              <div className="space-y-3 text-sm text-gray-700 dark:text-gray-300">
                <p className="font-semibold">试试这样说：</p>
                <button
                  onClick={() => setInput('帮我找北京的产品经理工作')}
                  className="block w-full text-left px-4 py-3 glass rounded-xl hover:bg-primary-50/50 dark:hover:bg-dark-600/50 border border-primary-200/50 dark:border-primary-700/50 transition-all card-hover"
                >
                  💼 "帮我找北京的产品经理工作"
                </button>
                <button
                  onClick={() => setInput('如何优化我的简历？')}
                  className="block w-full text-left px-4 py-3 glass rounded-xl hover:bg-primary-50/50 dark:hover:bg-dark-600/50 border border-primary-200/50 dark:border-primary-700/50 transition-all card-hover"
                >
                  📝 "如何优化我的简历？"
                </button>
                <button
                  onClick={() => setInput('互联网行业前景如何？')}
                  className="block w-full text-left px-4 py-3 glass rounded-xl hover:bg-primary-50/50 dark:hover:bg-dark-600/50 border border-primary-200/50 dark:border-primary-700/50 transition-all card-hover"
                >
                  💡 "互联网行业前景如何？"
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

          {/* Loading indicator */}
          {loading && isThinking && (
            <div className="flex justify-start animate-fade-in">
              <ThinkingIndicator />
            </div>
          )}

          {loading && !isThinking && (
            <div className="flex justify-start animate-fade-in">
              <div className="glass shadow-md rounded-2xl p-4 max-w-[80%] border border-primary-200/50 dark:border-primary-700/50">
                <div className="flex items-center gap-3">
                  <Bot className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                  <div className="loading-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area - 玻璃态 */}
        <div className="space-y-3">
          {/* Chat Input */}
          <div className="glass rounded-2xl shadow-lg p-4 border border-primary-200/50 dark:border-primary-700/50">
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
              className="flex-1 px-4 py-3 border-2 border-gray-300 dark:border-dark-500
                         bg-white dark:bg-dark-600 text-gray-900 dark:text-white
                         rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:opacity-50
                         transition-all duration-200 hover:border-primary-400 dark:hover:border-primary-600
                         resize-none overflow-y-auto"
            />
            {loading ? (
              <button
                onClick={cancelStream}
                className="p-3 bg-red-500 hover:bg-red-600 text-white rounded-xl
                           flex items-center justify-center shadow-lg hover:shadow-glow
                           transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98]"
                title="停止生成"
              >
                <Square className="w-5 h-5" />
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                className="p-3 bg-gradient-to-r from-primary-600 to-primary-500 text-white rounded-xl
                           hover:from-primary-700 hover:to-primary-600
                           disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center shadow-lg hover:shadow-glow
                           transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98]"
                title="发送"
              >
                <Send className="w-5 h-5" />
              </button>
            )}
          </div>
          <p className="text-xs text-gray-600 dark:text-gray-400 mt-2 text-center">
            AI助手可能会生成不准确的信息，请谨慎参考
          </p>
        </div>
        </div>
        </main>
      </div>
    </div>
  );
}
