'use client';

import {
  createContext,
  useContext,
  useState,
  useRef,
  useCallback,
  useEffect,
  type ReactNode,
} from 'react';
import { chatAPI } from '@/lib/api';
import { toast } from 'sonner';

// ── Types ──────────────────────────────────────────────
export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

interface ChatCache {
  messages: Message[];
  loaded: boolean;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  jobs?: any[];
  timestamp: Date;
  isError?: boolean;
}

interface ChatContextType {
  sessionId: string | null;
  sessions: Session[];
  messages: Message[];
  loading: boolean;
  isInitialized: boolean;
  isThinking: boolean;
  completedMessages: Set<string>;
  markMessageComplete: (messageId: string) => void;
  sendMessage: (content: string) => void;
  cancelStream: () => void;
  newChat: () => void;
  switchSession: (sessionId: string) => void;
  deleteSession: (sessionId: string) => Promise<void>;
  ensureSession: () => void;
}

const ChatContext = createContext<ChatContextType | null>(null);

export function useChat() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error('useChat must be used inside <ChatProvider>');
  return ctx;
}

// ── Utility: Strip Agent internal thinking text ──
// Defense layer: removes leading English-only paragraphs that leak from Agent reasoning
function stripThinkingText(content: string): string {
  if (!content) return content;
  
  // Split by paragraphs (double newline or single newline)
  const paragraphs = content.split(/\n\n+/);
  
  // Chinese character detection regex
  const hasChinese = /[\u4e00-\u9fff]/;
  
  // Find the first paragraph that contains Chinese text
  let startIdx = 0;
  for (let i = 0; i < paragraphs.length; i++) {
    const p = paragraphs[i].trim();
    if (!p) { startIdx = i + 1; continue; } // skip empty paragraphs
    if (hasChinese.test(p)) break; // found real content
    // Pure English paragraph at the start → likely thinking text
    startIdx = i + 1;
  }
  
  // If we stripped everything, return original (don't lose content)
  if (startIdx >= paragraphs.length) return content;
  
  return paragraphs.slice(startIdx).join('\n\n').trim();
}

// ── Provider ───────────────────────────────────────────
export function ChatProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);
  const [isThinking, setIsThinking] = useState(false);  // 新增
  const [completedMessages, setCompletedMessages] = useState<Set<string>>(new Set());  // 新增：已完成的消息

  const abortRef = useRef<AbortController | null>(null);
  // Track whether we already restored history for the current session
  const restoredSessionRef = useRef<string | null>(null);
  // Promise that resolves once initialization is complete
  const initPromiseRef = useRef<Promise<void> | null>(null);
  // Cache for loaded session messages
  const messageCacheRef = useRef<Map<string, ChatCache>>(new Map());
  // ✅ 防止 401 死循环：记录是否已经处理过认证失败
  const authFailedRef = useRef<boolean>(false);
  // ✅ 防止 Strict Mode 导致 useEffect 重复执行
  const isMountedRef = useRef<boolean>(false);

  // ── Restore session from localStorage on mount ──
  useEffect(() => {
    // ✅ 防止 React Strict Mode 导致重复执行
    if (isMountedRef.current) return;
    isMountedRef.current = true;
    
    const run = async () => {
      // ✅ 如果已经认证失败，直接跳过
      if (authFailedRef.current) return;
      
      try {
        await loadSessions();
      } catch (err) {
        // loadSessions 内部已经处理了 401
        return;
      }
      
      // ✅ 只有 loadSessions 成功后才加载消息
      if (!authFailedRef.current) {
        const savedId = localStorage.getItem('chat_session_id');
        if (savedId) {
          setSessionId(savedId);
          initPromiseRef.current = loadMessages(savedId);
        } else {
          setIsInitialized(true);
          initPromiseRef.current = Promise.resolve();
        }
      }
    };
    
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Load sessions list ──
  const loadSessions = async () => {
    // ✅ 如果已经处理过 401，不再重试
    if (authFailedRef.current) {
      console.warn('[ChatContext] Auth already failed, skipping loadSessions');
      return;
    }
    
    try {
      const res = await chatAPI.getSessions();
      setSessions(res.data);
    } catch (err: any) {
      console.error('Failed to load sessions:', err);
      // ✅ 401 已经在 axios 拦截器中处理，这里只需设置标志
      if (err.response?.status === 401) {
        authFailedRef.current = true;
        return; // ✅ 立即返回
      }
    }
  };

  // ── Load messages from backend ──
  const loadMessages = async (sid: string): Promise<void> => {
    if (restoredSessionRef.current === sid) return;
    
    // ✅ 如果已经处理过 401，不再重试
    if (authFailedRef.current) {
      console.warn('[ChatContext] Auth already failed, skipping loadMessages');
      setIsInitialized(true);
      return;
    }
    
    try {
      const res = await chatAPI.getMessages(sid);
      const mapped: Message[] = res.data.map((m: any) => ({
        id: m.id,
        role: m.role as 'user' | 'assistant',
        content: m.content,
        jobs: m.message_metadata?.jobs,
        timestamp: new Date(m.created_at),
      }));
      setMessages(mapped);
      restoredSessionRef.current = sid;
    } catch (err: any) {
      console.error('Failed to load chat messages:', err);
      // ✅ 401 已经在 axios 拦截器中处理，这里只需设置标志
      if (err.response?.status === 401) {
        authFailedRef.current = true;
        return; // ✅ 立即返回
      }
    } finally {
      setIsInitialized(true);
    }
  };

  // ── Create a new session ─
  const createSession = async (): Promise<string | null> => {
    // ✅ 如果已经处理过 401，不再重试
    if (authFailedRef.current) {
      console.warn('[ChatContext] Auth already failed, skipping createSession');
      return null;
    }
    
    try {
      const res = await chatAPI.createSession();
      const id = res.data.id;
      setSessionId(id);
      localStorage.setItem('chat_session_id', id);
      restoredSessionRef.current = id;
      return id;
    } catch (err: any) {
      console.error('Failed to create chat session:', err);
      // ✅ 401 已经在 axios 拦截器中处理，这里只需设置标志
      if (err.response?.status === 401) {
        authFailedRef.current = true;
        return null; // ✅ 立即返回
      }
      return null;
    }
  };

  // ── Ensure a session exists (called by chat page) ──
  const ensureSession = useCallback(async () => {
    // Wait for localStorage restoration to complete first
    if (initPromiseRef.current) {
      await initPromiseRef.current;
    }
    // After restoration, check if we need a new session
    const currentId = localStorage.getItem('chat_session_id');
    if (!currentId) {
      await createSession();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Switch to another session ──
  const switchSession = useCallback(async (targetSessionId: string) => {
    if (targetSessionId === sessionId) return;
    
    // ✅ 如果已经处理过 401，不再重试
    if (authFailedRef.current) {
      console.warn('[ChatContext] Auth already failed, skipping switchSession');
      return;
    }

    // 1. Abort current stream
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);

    // 2. Save current session messages to cache before switching
    if (sessionId) {
      messageCacheRef.current.set(sessionId, {
        messages,
        loaded: true,
      });
    }

    // 3. Switch to target session
    setSessionId(targetSessionId);
    localStorage.setItem('chat_session_id', targetSessionId);

    // 4. Check cache first
    const cached = messageCacheRef.current.get(targetSessionId);
    if (cached && cached.loaded) {
      setMessages(cached.messages);
      setIsInitialized(true);
      return;
    }

    // 5. Load from backend if not cached
    setIsInitialized(false);
    try {
      const res = await chatAPI.getMessages(targetSessionId);
      const mapped: Message[] = res.data.map((m: any) => ({
        id: m.id,
        role: m.role as 'user' | 'assistant',
        content: m.content,
        jobs: m.message_metadata?.jobs,
        timestamp: new Date(m.created_at),
      }));
      setMessages(mapped);
      messageCacheRef.current.set(targetSessionId, {
        messages: mapped,
        loaded: true,
      });
    } catch (err: any) {
      console.error('Failed to load messages:', err);
      // ✅ 401 已经在 axios 拦截器中处理，这里只需设置标志
      if (err.response?.status === 401) {
        authFailedRef.current = true;
        return;
      }
      setMessages([]);
    } finally {
      setIsInitialized(true);
      restoredSessionRef.current = targetSessionId;
    }
  }, [sessionId, messages]);

  // ── Delete a session ──
  const deleteSession = useCallback(async (targetSessionId: string) => {
    // ✅ 如果已经处理过 401,不再重试
    if (authFailedRef.current) {
      console.warn('[ChatContext] Auth already failed, skipping deleteSession');
      return;
    }
      
    try {
      await chatAPI.deleteSession(targetSessionId);
  
      // Remove from cache
      messageCacheRef.current.delete(targetSessionId);
  
      // Refresh session list
      await loadSessions();
  
      // If deleted session was the current one, switch to another or create new
      if (targetSessionId === sessionId) {
        const remaining = sessions.filter((s) => s.id !== targetSessionId);
        if (remaining.length > 0) {
          // Switch to the most recent remaining session
          await switchSession(remaining[0].id);
        } else {
          // No sessions left, create a new one
          await newChat();
        }
      }
    } catch (err: any) {
      console.error('Failed to delete session:', err);
        
      // ✅ 401 已经在 axios 拦截器中处理,会自动跳转登录
      if (err.response?.status === 401) {
        authFailedRef.current = true;
        return;
      }
        
      toast.error('删除会话失败');
    }
  }, [sessionId, sessions]);

  // ─ Mark message as complete ──
  const markMessageComplete = useCallback((messageId: string) => {
    setCompletedMessages((prev) => new Set(prev).add(messageId));
  }, []);

  // ── Send message ──
  const sendMessage = useCallback(
    (content: string) => {
      if (!sessionId || loading) return;

      // Abort previous stream if any
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const userMsg: Message = {
        id: `user-${Date.now()}`,
        role: 'user',
        content,
        timestamp: new Date(),
      };

      const assistantId = `assistant-${Date.now() + 1}`;
      const assistantMsg: Message = {
        id: assistantId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setLoading(true);
      setIsThinking(true);  // 开始思考

      chatAPI.sendMessageStream(
        sessionId,
        content,
        // onToken
        (token: string) => {
          // 收到第一个 token 时，停止 thinking 指示器
          if (isThinking) {
            setIsThinking(false);
          }
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + token } : m
            )
          );
        },
        // onJobResults — structured job data arrives via an independent SSE event
        (jobs: any[]) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, jobs } : m
            )
          );
        },
        // onComplete
        () => {
          setLoading(false);
          setIsThinking(false);  // 确保 thinking 状态关闭
          // ✅ 防御层：清理可能泄露的 Agent 英文思维文本
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: stripThinkingText(m.content) } : m
            )
          );
          // 标记该 assistant 消息已完成
          markMessageComplete(assistantId);
          abortRef.current = null;
        },
        // onError
        (error: string) => {
          // ✅ 401 已经在 axios 拦截器中处理，这里只需设置标志
          if (error.includes('401') || error.includes('Unauthorized')) {
            authFailedRef.current = true;
            return;
          }
          
          // Distinguish abort from real error
          if (controller.signal.aborted) {
            // Stream was intentionally cancelled (e.g. new chat), remove placeholder
            setMessages((prev) => prev.filter((m) => m.id !== assistantId));
            setLoading(false);
            setIsThinking(false);
            return;
          }
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: '抱歉，发生了错误。请稍后重试。', isError: true }
                : m
            )
          );
          setLoading(false);
          setIsThinking(false);  // 确保 thinking 状态关闭
          abortRef.current = null;
        },
        controller.signal
      );
    },
    [sessionId, loading]
  );

  // ── Cancel stream ──
  const cancelStream = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
    setIsThinking(false);
  }, []);

  // ── New chat ──
  const newChat = useCallback(async () => {
    // Cancel any in-flight SSE
    abortRef.current?.abort();
    abortRef.current = null;

    setMessages([]);
    setLoading(false);
    restoredSessionRef.current = null;

    const id = await createSession();
    if (id) {
      restoredSessionRef.current = id;
      // Refresh session list to include the new one
      await loadSessions();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <ChatContext.Provider
      value={{
        sessionId,
        sessions,
        messages,
        loading,
        isInitialized,
        isThinking,
        completedMessages,
        markMessageComplete,
        sendMessage,
        cancelStream,
        newChat,
        switchSession,
        deleteSession,
        ensureSession,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}
