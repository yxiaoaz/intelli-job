'use client';

import { useChat, type Session } from './ChatContext';
import { PlusCircle, MessageSquare, Trash2 } from 'lucide-react';
import Button from '@/components/ui/Button';

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
    <aside className="w-64 bg-layer1 border-r border-l1 flex flex-col h-screen sticky top-0">
      {/* New Chat Button */}
      <div className="p-4 border-b border-l1 flex-shrink-0">
        <Button onClick={newChat} variant="primary" size="sm" className="w-full">
          <PlusCircle className="w-4 h-4" />
          新对话
        </Button>
      </div>

      {/* Session List - Independent scrolling */}
      <div className="flex-1 overflow-y-auto p-2 space-y-3">
        {sessions.length === 0 ? (
          <div className="text-center py-8 text-500 text-sm">
            暂无历史对话
          </div>
        ) : (
          groupSessionsByTime().map((group) => (
            <div key={group.label}>
              {/* Group Label */}
              <div className="px-3 py-1 text-xs font-medium text-500 uppercase tracking-wider">
                {group.label}
              </div>
              
              {/* Sessions in this group */}
              <div className="space-y-1">
                {group.sessions.map((session) => (
                  <div
                    key={session.id}
                    className={`group flex items-center rounded-menu transition-colors duration-base ease-ds ${
                      sessionId === session.id
                        ? 'bg-tint-primary border-l-4 border-primary-500'
                        : 'hover:bg-hover-neutral'
                    }`}
                  >
                    <button
                      onClick={() => switchSession(session.id)}
                      className="flex-1 text-left px-3 py-2 min-w-0"
                    >
                      <div className="flex items-start gap-2">
                        <MessageSquare className="w-4 h-4 text-500 flex-shrink-0 mt-0.5" />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-900 truncate">
                            {session.title || '未命名对话'}
                          </div>
                          <div className="text-xs text-500 mt-0.5">
                            {formatTime(session.updated_at)}
                          </div>
                        </div>
                      </div>
                    </button>
                    {/* Delete Button - Only show on hover */}
                    <button
                      onClick={(e) => handleDelete(e, session.id)}
                      className="opacity-0 group-hover:opacity-100 p-2 text-400 hover:text-danger-600 transition-opacity"
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
