'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useChat } from '@/components/ChatContext';
import { ChatSidebar } from '@/components/ChatSidebar';
import ResumeStatusCard from '@/components/ResumeStatusCard';
import IntentDisplay from '@/components/IntentDisplay';
import ThinkingIndicator from '@/components/ThinkingIndicator';
import JobDetailModal from '@/components/JobDetailModal';
import JobCard from '@/components/JobCard';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Send, Bot, User, Sparkles, Briefcase, MapPin, DollarSign } from 'lucide-react';

export default function ChatPage() {
  const router = useRouter();
  const { 
    sessions, sessionId, messages, loading, isInitialized, isThinking,
    sendMessage, newChat, switchSession, ensureSession, completedMessages, markMessageComplete
  } = useChat();
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const [isUserAtBottom, setIsUserAtBottom] = useState(true);
  
  // Job Detail Modal State
  const [selectedJob, setSelectedJob] = useState<any>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  
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

  const handleSend = () => {
    if (!input.trim() || loading) return;
    sendMessage(input);
    setInput('');
  };

  const handleNewChat = () => {
    newChat();
  };

  // Parse job data from assistant message
  const parseJobsFromMessage = (content: string): any[] => {
    try {
      // Look for JSON code block
      const jsonMatch = content.match(/```json\s*([\s\S]*?)\s*```/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[1]);
        if (parsed.jobs && Array.isArray(parsed.jobs)) {
          return parsed.jobs;
        }
      }
      
      // Fallback 1: Try to find inline JSON (支持嵌套花括号)
      const inlineMatch = content.match(/\{[\s\S]*?"jobs"[\s\S]*?\}(?=\s*$|\s*```)/);
      if (inlineMatch) {
        const parsed = JSON.parse(inlineMatch[0]);
        if (parsed.jobs && Array.isArray(parsed.jobs)) {
          return parsed.jobs;
        }
      }
      
      // Fallback 2: Try to find any JSON object with jobs array
      const anyJsonMatch = content.match(/\{[^{}]*"jobs"\s*:[^{}]*\}/);
      if (anyJsonMatch) {
        try {
          const parsed = JSON.parse(anyJsonMatch[0]);
          if (parsed.jobs && Array.isArray(parsed.jobs)) {
            return parsed.jobs;
          }
        } catch (e) {
          console.warn('Fallback JSON parse failed:', e);
        }
      }
    } catch (err) {
      console.error('Failed to parse jobs:', err);
    }
    return [];
  };

  // Extract clean text without job JSON
  const extractCleanText = (content: string, messageId: string): string => {
    const isCompleted = completedMessages.has(messageId);
    
    if (!isCompleted) {
      // 流式输出期间:移除所有 JSON 相关代码块
      return content
        .replace(/```[\s\S]*$/g, '')  // 移除未完成的代码块
        .replace(/\{[\s\S]*"jobs"[\s\S]*$/g, '')  // 移除包含 jobs 的 JSON
        .replace(/```json[\s\S]*$/g, '')  // 移除 json 标记
        .trim();
    }
    
    // 流完成后:正常移除完整的 JSON 代码块
    let text = content.replace(/```json\s*[\s\S]*?\s*```/g, '');
    // Remove inline JSON with jobs
    text = text.replace(/\{[\s\S]*?"jobs"\s*:[\s\S]*?\}(?=\s*$|\s*```)/g, '');
    
    return text.trim();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-dark-50 via-white to-primary-50 dark:from-dark-900 dark:via-dark-800 dark:to-dark-900 flex animate-fade-in">
      {/* Sidebar */}
      <ChatSidebar />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header - 玻璃态 */}
        <header className="glass shadow-md sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
            <h1 className="text-2xl font-bold gradient-text font-display">Intelli-Job AI助手</h1>
            <nav className="space-x-6">
              <button
                onClick={() => router.push('/dashboard')}
                className="text-gray-700 dark:text-gray-300 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
              >
                职位搜索
              </button>
              <button
                onClick={() => router.push('/resumes')}
                className="text-gray-700 dark:text-gray-300 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
              >
                我的简历
              </button>
              <button
                onClick={() => router.push('/chat')}
                className="text-primary-600 dark:text-primary-400 font-semibold"
              >
                AI助手
              </button>
              <button
                onClick={() => router.push('/profile')}
                className="text-gray-700 dark:text-gray-300 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
              >
                我的资料
              </button>
              <button
                onClick={() => {
                  localStorage.removeItem('access_token');
                  localStorage.removeItem('refresh_token');
                  router.push('/login');
                }}
                className="text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 transition-colors"
              >
                退出
              </button>
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
          {!isInitialized ? (
            <div className="text-center py-12">
              <div className="loading-dots mx-auto">
                <span></span><span></span><span></span>
              </div>
            </div>
          ) : messages.length === 0 ? (
            <div className="text-center py-12 animate-fade-in">
              <div className="text-primary-400 text-7xl mb-4 animate-pulse-slow">🤖</div>
              <p className="text-gray-700 dark:text-gray-300 text-xl font-semibold mb-2">你好！我是你的求职助手</p>
              <p className="text-gray-600 dark:text-gray-400 text-sm">
                我可以帮你搜索职位、分析简历、提供求职建议
              </p>
              <div className="mt-8 space-y-3 text-sm text-gray-700 dark:text-gray-300">
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
            messages.map((message) => {
              const jobs = message.role === 'assistant' ? parseJobsFromMessage(message.content) : [];
              const cleanContent = message.role === 'assistant' ? extractCleanText(message.content, message.id) : message.content;

              return (
                <div
                  key={message.id}
                  className={`flex ${
                    message.role === 'user' ? 'justify-end' : 'justify-start'
                  } animate-fade-in`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl p-5 ${
                      message.role === 'user'
                        ? 'bg-gradient-to-r from-primary-600 to-primary-500 text-white shadow-lg'
                        : 'glass shadow-md border border-primary-200/50 dark:border-primary-700/50'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {message.role === 'assistant' && (
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center flex-shrink-0 shadow-md">
                          <Bot className="w-5 h-5 text-white" />
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        {/* Clean text content with Markdown rendering */}
                        {cleanContent && (
                          <div className="prose prose-sm dark:prose-invert max-w-none mb-4">
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              components={{
                                // 自定义样式
                                h1: ({node, ...props}) => <h1 className="text-xl font-bold mb-2 text-gray-900 dark:text-white" {...props} />,
                                h2: ({node, ...props}) => <h2 className="text-lg font-bold mb-2 text-gray-900 dark:text-white" {...props} />,
                                h3: ({node, ...props}) => <h3 className="text-base font-bold mb-2 text-gray-900 dark:text-white" {...props} />,
                                ul: ({node, ...props}) => <ul className="list-disc list-inside mb-2 space-y-1" {...props} />,
                                ol: ({node, ...props}) => <ol className="list-decimal list-inside mb-2 space-y-1" {...props} />,
                                li: ({node, ...props}) => <li className="text-gray-700 dark:text-gray-300" {...props} />,
                                strong: ({node, ...props}) => <strong className="font-bold text-gray-900 dark:text-white" {...props} />,
                                em: ({node, ...props}) => <em className="italic text-gray-700 dark:text-gray-300" {...props} />,
                                p: ({node, ...props}) => <p className="mb-2 text-gray-700 dark:text-gray-300 leading-relaxed" {...props} />,
                                code: ({node, inline, className, children, ...props}: any) => 
                                  inline ? (
                                    <code className="px-1.5 py-0.5 bg-gray-100 dark:bg-dark-600 rounded text-sm font-mono text-gray-800 dark:text-gray-200" {...props}>
                                      {children}
                                    </code>
                                  ) : (
                                    <code className="block bg-gray-100 dark:bg-dark-600 rounded-lg p-3 text-sm font-mono text-gray-800 dark:text-gray-200 overflow-x-auto my-2" {...props}>
                                      {children}
                                    </code>
                                  ),
                                pre: ({node, ...props}) => <pre className="bg-gray-100 dark:bg-dark-600 rounded-lg p-3 overflow-x-auto my-2" {...props} />,
                                blockquote: ({node, ...props}) => <blockquote className="border-l-4 border-primary-400 pl-4 italic text-gray-600 dark:text-gray-400 my-2" {...props} />,
                                a: ({node, ...props}) => <a className="text-primary-600 dark:text-primary-400 hover:underline" {...props} />,
                              }}
                            >
                              {cleanContent}
                            </ReactMarkdown>
                          </div>
                        )}
                        
                        {/* Job cards grid */}
                        {jobs.length > 0 && (
                          <div className="mt-4">
                            <div className="flex items-center gap-2 mb-4">
                              <Sparkles className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                              <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                                找到 {jobs.length} 个匹配岗位
                              </h3>
                            </div>
                            
                            {/* Grid layout for job cards */}
                            <div className="grid grid-cols-1 gap-4">
                              {jobs.slice(0, 5).map((job: any, idx: number) => {
                                // ✅ 修复：为 Chat 的 job 对象添加缺失字段，使其与 Dashboard 兼容
                                const enhancedJob = {
                                  ...job,
                                  // 兼容 JobDetailModal 的字段映射
                                  description: job.description || '',  // 截断版
                                  full_description: job.description || '',  // 完整版（Chat 中两者相同）
                                  recruitment_type: job.recruitment_type || '未知',
                                  education: job.education || '不限',
                                  update_time: job.update_time || '',
                                  score: job.match_score || 0,
                                  is_bookmarked: false,
                                };
                                
                                return (
                                  <JobCard
                                    key={idx}
                                    job={enhancedJob}
                                    index={idx}
                                    onClick={() => {
                                      setSelectedJob(enhancedJob);
                                      setIsModalOpen(true);
                                    }}
                                  />
                                );
                              })}
                            </div>
                            
                            {jobs.length > 5 && (
                              <div className="mt-4 text-center">
                                <button
                                  onClick={() => {
                                    // TODO: 加载更多岗位
                                  }}
                                  className="px-6 py-3 bg-gradient-to-r from-primary-600 to-primary-500 text-white rounded-xl hover:from-primary-700 hover:to-primary-600 transition-all shadow-lg hover:shadow-xl font-semibold"
                                >
                                  查看全部 {jobs.length} 个岗位
                                </button>
                              </div>
                            )}
                          </div>
                        )}
                        
                        <p
                          className={`text-xs mt-3 ${
                            message.role === 'user'
                              ? 'text-primary-100'
                              : 'text-gray-500 dark:text-gray-400'
                          }`}
                        >
                          {message.timestamp.toLocaleTimeString()}
                        </p>
                      </div>
                      {message.role === 'user' && (
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-400 to-primary-500 flex items-center justify-center flex-shrink-0 shadow-md">
                          <User className="w-5 h-5 text-white" />
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
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
          {/* Resume Status Card */}
          {sessionId && (
            <ResumeStatusCard 
              sessionId={sessionId}
              onUploadSuccess={(resumeId) => {
                console.log('Resume uploaded:', resumeId);
              }}
            />
          )}

          {/* Intent Display */}
          {sessionId && (
            <IntentDisplay 
              sessionId={sessionId}
              onIntentChange={(intent) => {
                console.log('Intent updated:', intent);
              }}
            />
          )}

          {/* Chat Input */}
          <div className="glass rounded-2xl shadow-lg p-4 border border-primary-200/50 dark:border-primary-700/50">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              placeholder="输入消息..."
              disabled={loading}
              className="flex-1 px-4 py-3 border-2 border-gray-300 dark:border-dark-500
                         bg-white dark:bg-dark-600 text-gray-900 dark:text-white
                         rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:opacity-50
                         transition-all duration-200 hover:border-primary-400 dark:hover:border-primary-600"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || loading}
              className="px-6 py-3 bg-gradient-to-r from-primary-600 to-primary-500 text-white rounded-xl hover:from-primary-700 hover:to-primary-600
                         disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 font-semibold shadow-lg hover:shadow-glow
                         transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98]"
            >
              <Send className="w-4 h-4" />
              发送
            </button>
          </div>
          <p className="text-xs text-gray-600 dark:text-gray-400 mt-2 text-center">
            AI助手可能会生成不准确的信息，请谨慎参考
          </p>
        </div>
        </div>
        </main>
        
        {/* Job Detail Modal */}
        {selectedJob && (
          <JobDetailModal
            job={selectedJob}
            isOpen={isModalOpen}
            onClose={() => {
              setIsModalOpen(false);
              setSelectedJob(null);
            }}
            source="chat"
          />
        )}
      </div>
    </div>
  );
}
