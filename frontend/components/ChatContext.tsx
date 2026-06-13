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
  timestamp: Date;
}

interface ChatContextType {
  sessionId: string | null;
  sessions: Session[];          // 新增
  messages: Message[];
  loading: boolean;
  isInitialized: boolean;
  isThinking: boolean;          // 新增：模型思考状态
  completedMessages: Set<string>;  // 新增：已完成的消息ID集合
  markMessageComplete: (messageId: string) => void;  // 新增：标记消息完成
  sendMessage: (content: string) => void;
  newChat: () => void;
  switchSession: (sessionId: string) => void;  // 新增
  deleteSession: (sessionId: string) => Promise<void>;  // 新增
  /** Called by chat page to ensure a session exists */
  ensureSession: () => void;
}

const ChatContext = createContext<ChatContextType | null>(null);

export function useChat() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error('useChat must be used inside <ChatProvider>');
  return ctx;
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
        
      alert('删除会话失败');
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
        // onComplete
        () => {
          setLoading(false);
          setIsThinking(false);  // 确保 thinking 状态关闭
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
                ? { ...m, content: '抱歉，发生了错误。请稍后重试。' }
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
        sessions,       // 新增
        messages,
        loading,
        isInitialized,
        isThinking,     // 新增
        completedMessages,  // 新增
        markMessageComplete,  // 新增
        sendMessage,
        newChat,
        switchSession,  // 新增
        deleteSession,  // 新增
        ensureSession,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}
