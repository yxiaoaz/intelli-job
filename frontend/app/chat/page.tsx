'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useChat } from '@/components/ChatContext';
import { ChatSidebar } from '@/components/ChatSidebar';
import { Send, Bot, User } from 'lucide-react';

export default function ChatPage() {
  const router = useRouter();
  const { 
    sessions, sessionId, messages, loading, isInitialized, 
    sendMessage, newChat, switchSession, ensureSession 
  } = useChat();
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Check authentication and ensure session exists on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/login');
      return;
    }
    ensureSession();
  }, [router, ensureSession]);

  // Auto scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || loading) return;
    sendMessage(input);
    setInput('');
  };

  const handleNewChat = () => {
    newChat();
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
        <div className="flex-1 space-y-4 mb-4 overflow-y-auto">
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
            messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                } animate-fade-in`}
              >
                <div
                  className={`max-w-[80%] rounded-2xl p-4 ${
                    message.role === 'user'
                      ? 'bg-gradient-to-r from-primary-600 to-primary-500 text-white shadow-lg'
                      : 'glass shadow-md border border-primary-200/50 dark:border-primary-700/50'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {message.role === 'assistant' && (
                      <Bot className="w-5 h-5 text-primary-600 dark:text-primary-400 flex-shrink-0 mt-1" />
                    )}
                    <div className="flex-1">
                      <p className="whitespace-pre-wrap">{message.content}</p>
                      <p
                        className={`text-xs mt-2 ${
                          message.role === 'user'
                            ? 'text-primary-100'
                            : 'text-gray-600 dark:text-gray-400'
                        }`}
                      >
                        {message.timestamp.toLocaleTimeString()}
                      </p>
                    </div>
                    {message.role === 'user' && (
                      <User className="w-5 h-5 text-primary-100 flex-shrink-0 mt-1" />
                    )}
                  </div>
                </div>
              </div>
            ))
          )}

          {/* Loading indicator */}
          {loading && (
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
        </main>
      </div>
    </div>
  );
}
