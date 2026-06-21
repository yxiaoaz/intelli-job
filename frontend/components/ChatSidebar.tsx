'use client';

import { useChat, type Session } from './ChatContext';
import { PlusCircle, MessageSquare, Trash2 } from 'lucide-react';

export function ChatSidebar() {
  const { sessions, sessionId, newChat, switchSession, deleteSession } = useChat();

  const handleDelete = async (e: React.MouseEvent, sessionToDeleteId: string) => {
    e.stopPropagation(); // Prevent switching when clicking delete
    if (window.confirm('确定要删除这个对话吗？')) {
      await deleteSession(sessionToDeleteId);
    }
  };

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return '今天';
    if (diffDays === 1) return '昨天';
    if (diffDays < 7) return `${diffDays}天前`;
    return date.toLocaleDateString('zh-CN');
  };

  // Group sessions by time
  const groupSessionsByTime = () => {
    const now = new Date();
    const groups: { label: string; sessions: Session[] }[] = [
      { label: '今天', sessions: [] },
      { label: '昨天', sessions: [] },
      { label: '7天内', sessions: [] },
      { label: '更早', sessions: [] },
    ];

    sessions.forEach((session) => {
      const date = new Date(session.updated_at);
      const diffMs = now.getTime() - date.getTime();
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

      if (diffDays === 0) {
        groups[0].sessions.push(session);
      } else if (diffDays === 1) {
        groups[1].sessions.push(session);
      } else if (diffDays < 7) {
        groups[2].sessions.push(session);
      } else {
        groups[3].sessions.push(session);
      }
    });

    // Filter out empty groups
    return groups.filter((group) => group.sessions.length > 0);
  };

  return (
    <aside className="w-64 bg-white dark:bg-dark-800 border-r border-gray-200 dark:border-dark-600 flex flex-col h-screen sticky top-0">
      {/* New Chat Button */}
      <div className="p-4 border-b border-gray-200 dark:border-dark-600 flex-shrink-0">
        <button
          onClick={newChat}
          className="w-full px-4 py-2 bg-gradient-to-r from-primary-600 to-primary-500 text-white rounded-xl hover:from-primary-700 hover:to-primary-600 flex items-center justify-center gap-2 font-semibold shadow-lg transition-all"
        >
          <PlusCircle className="w-4 h-4" />
          新对话
        </button>
      </div>

      {/* Session List - Independent scrolling */}
      <div className="flex-1 overflow-y-auto p-2 space-y-3">
        {sessions.length === 0 ? (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
            暂无历史对话
          </div>
        ) : (
          groupSessionsByTime().map((group) => (
            <div key={group.label}>
              {/* Group Label */}
              <div className="px-3 py-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                {group.label}
              </div>
              
              {/* Sessions in this group */}
              <div className="space-y-1">
                {group.sessions.map((session) => (
                  <div
                    key={session.id}
                    className={`group flex items-center rounded-lg transition-all ${
                      sessionId === session.id
                        ? 'bg-primary-50 dark:bg-primary-900/30 border-l-4 border-primary-500'
                        : 'hover:bg-gray-50 dark:hover:bg-dark-700'
                    }`}
                  >
                    <button
                      onClick={() => switchSession(session.id)}
                      className="flex-1 text-left px-3 py-2 min-w-0"
                    >
                      <div className="flex items-start gap-2">
                        <MessageSquare className="w-4 h-4 text-gray-500 dark:text-gray-400 flex-shrink-0 mt-0.5" />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-900 dark:text-white truncate">
                            {session.title || '未命名对话'}
                          </div>
                          <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                            {formatTime(session.updated_at)}
                          </div>
                        </div>
                      </div>
                    </button>
                    {/* Delete Button - Only show on hover */}
                    <button
                      onClick={(e) => handleDelete(e, session.id)}
                      className="opacity-0 group-hover:opacity-100 p-2 text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-opacity"
                      title="删除对话"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
