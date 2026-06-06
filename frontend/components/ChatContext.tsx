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

  const abortRef = useRef<AbortController | null>(null);
  // Track whether we already restored history for the current session
  const restoredSessionRef = useRef<string | null>(null);
  // Promise that resolves once initialization is complete
  const initPromiseRef = useRef<Promise<void> | null>(null);
  // Cache for loaded session messages
  const messageCacheRef = useRef<Map<string, ChatCache>>(new Map());

  // ── Restore session from localStorage on mount ──
  useEffect(() => {
    loadSessions();  // 新增
    const savedId = localStorage.getItem('chat_session_id');
    if (savedId) {
      setSessionId(savedId);
      initPromiseRef.current = loadMessages(savedId);
    } else {
      setIsInitialized(true);
      initPromiseRef.current = Promise.resolve();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Load sessions list ──
  const loadSessions = async () => {
    try {
      const res = await chatAPI.getSessions();
      setSessions(res.data);
    } catch (err) {
      console.error('Failed to load sessions:', err);
    }
  };

  // ── Load messages from backend ──
  const loadMessages = async (sid: string): Promise<void> => {
    if (restoredSessionRef.current === sid) return;
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
    } catch (err) {
      console.error('Failed to load chat messages:', err);
    } finally {
      setIsInitialized(true);
    }
  };

  // ── Create a new session ──
  const createSession = async (): Promise<string | null> => {
    try {
      const res = await chatAPI.createSession();
      const id = res.data.id;
      setSessionId(id);
      localStorage.setItem('chat_session_id', id);
      restoredSessionRef.current = id;
      return id;
    } catch (err) {
      console.error('Failed to create chat session:', err);
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
    } catch (err) {
      console.error('Failed to load messages:', err);
      setMessages([]);
    } finally {
      setIsInitialized(true);
      restoredSessionRef.current = targetSessionId;
    }
  }, [sessionId, messages]);

  // ── Delete a session ──
  const deleteSession = useCallback(async (targetSessionId: string) => {
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
    } catch (err) {
      console.error('Failed to delete session:', err);
      alert('删除会话失败');
    }
  }, [sessionId, sessions]);

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

      chatAPI.sendMessageStream(
        sessionId,
        content,
        // onToken
        (token: string) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + token } : m
            )
          );
        },
        // onComplete
        () => {
          setLoading(false);
          abortRef.current = null;
        },
        // onError
        (error: string) => {
          // Distinguish abort from real error
          if (controller.signal.aborted) {
            // Stream was intentionally cancelled (e.g. new chat), remove placeholder
            setMessages((prev) => prev.filter((m) => m.id !== assistantId));
            setLoading(false);
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
