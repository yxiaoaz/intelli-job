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

// ✅ ui-redesign 决策 10/13/16：工具调用状态机与结构化事件字段对齐
export interface ToolCall {
  id: string;              // 全轮唯一，如 "tc_018"；历史降级渲染时可缺省，用索引兜底
  name: string;            // "search_jobs"
  args?: unknown;          // tool_start 携带的原始参数，用于展开详情 IN 段
  status: 'running' | 'ok' | 'error' | 'stopped';
  resultSummary?: string;  // tool_end 下发，后端已截断至 200 字符
  resultRaw?: string;      // tool_end 下发，用于展开详情 OUT 段 head+tail（仅实时流可用）
  durationMs?: number;
  argsSummary?: string;    // 历史消息（tool_events）已算好的单行摘要，实时流走 summarizeArgs
  /** @deprecated 过渡期兼容旧 metadata.tool_calls（无 id/status 的单行降级渲染） */
  display?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  jobs?: any[];
  toolCalls?: ToolCall[];
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
  // ✅ 发送失败时保留的草稿（供页面恢复到输入框）
  pendingDraft: string | null;
  clearPendingDraft: () => void;
}

const ChatContext = createContext<ChatContextType | null>(null);

/**
 * ui-redesign 决策 16：历史消息降级映射。
 * 优先读 metadata.tool_events（结构化逐对事件）；缺失时按旧 metadata.tool_calls
 * 降级渲染单行 ok 态（无摘要无展开）。
 */
export function mapMetadataToToolCalls(metadata: any): ToolCall[] | undefined {
  if (!metadata) return undefined;
  const events = metadata.tool_events;
  if (Array.isArray(events) && events.length > 0) {
    return events.map((ev: any, i: number) => ({
      id: ev.id ?? `tc_hist_${i}`,
      name: ev.name,
      status: (ev.status === 'error' ? 'error' : 'ok') as ToolCall['status'],
      resultSummary: ev.result_summary,
      argsSummary: ev.args_summary,
      durationMs: ev.duration_ms,
    }));
  }
  const legacyCalls = metadata.tool_calls;
  if (Array.isArray(legacyCalls) && legacyCalls.length > 0) {
    return legacyCalls.map((c: any, i: number) => ({
      id: `tc_legacy_${i}`,
      name: c.name,
      status: 'ok' as const,
    }));
  }
  return undefined;
}

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
  // ✅ 用 ref 跟踪 isThinking，避免闭包捕获旧值
  const isThinkingRef = useRef(false);
  const [isThinking, setIsThinking] = useState(false);
  
  // 同步 ref 和 state
  const updateThinking = (val: boolean) => {
    isThinkingRef.current = val;
    setIsThinking(val);
  };
  const [completedMessages, setCompletedMessages] = useState<Set<string>>(new Set());  // 新增：已完成的消息
  // ✅ 发送失败时保留的草稿
  const [pendingDraft, setPendingDraft] = useState<string | null>(null);
  const clearPendingDraft = useCallback(() => setPendingDraft(null), []);

  const abortRef = useRef<AbortController | null>(null);
  // Track whether we already restored history for the current session
  const restoredSessionRef = useRef<string | null>(null);
  // Promise that resolves once initialization is complete
  const initPromiseRef = useRef<Promise<void> | null>(null);
  // Cache for loaded session messages
  const messageCacheRef = useRef<Map<string, ChatCache>>(new Map());
  // ✅ messages ref 用于 switchSession 缓存，避免 messages 在 deps 中导致每次 token 重建函数
  const messagesRef = useRef<Message[]>([]);
  // ✅ 防止 401 死循环：记录是否已经处理过认证失败
  const authFailedRef = useRef<boolean>(false);
  // ✅ 防止 Strict Mode 导致 useEffect 重复执行
  const isMountedRef = useRef<boolean>(false);
  // ✅ refs 跟踪最新函数引用，避免 deleteSession 闭包捕获旧版本
  const switchSessionRef = useRef<(id: string) => Promise<void>>();
  const newChatRef = useRef<() => Promise<void>>();
  const deletingRef = useRef(false);

  // ✅ 同步 messagesRef，供 switchSession 缓存使用
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

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
        // ✅ ui-redesign 决策 16：历史消息优先 tool_events，缺失降级 tool_calls
        toolCalls: mapMetadataToToolCalls(m.message_metadata),
        timestamp: new Date(m.created_at),
      }));
      setMessages(mapped);
      // ✅ 历史消息直接视为已完成：否则岗位卡/工具卡永远停在流式未完成态
      setCompletedMessages((prev) => {
        const next = new Set(prev);
        mapped.forEach((m) => next.add(m.id));
        return next;
      });
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
        messages: messagesRef.current,
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
        // ✅ ui-redesign 决策 16：与 loadMessages 保持一致
        toolCalls: mapMetadataToToolCalls(m.message_metadata),
        timestamp: new Date(m.created_at),
      }));
      setMessages(mapped);
      // ✅ 历史消息直接视为已完成（与 loadMessages 一致）
      setCompletedMessages((prev) => {
        const next = new Set(prev);
        mapped.forEach((m) => next.add(m.id));
        return next;
      });
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
  }, [sessionId]);
  // ✅ 同步 ref，供 deleteSession 使用最新版本
  switchSessionRef.current = switchSession;

  // ─ Delete a session ──
  const deleteSession = useCallback(async (targetSessionId: string) => {
    // ✅ 防止重复点击
    if (deletingRef.current) return;
    if (authFailedRef.current) {
      console.warn('[ChatContext] Auth already failed, skipping deleteSession');
      return;
    }

    deletingRef.current = true;
      
    try {
      // 1. 乐观更新：立即从列表中移除
      setSessions((prev) => prev.filter((s) => s.id !== targetSessionId));
      messageCacheRef.current.delete(targetSessionId);
  
      // 2. 调用后端删除
      await chatAPI.deleteSession(targetSessionId);
  
      // 3. 获取最新列表（兜底，确保与后端一致）
      const res = await chatAPI.getSessions();
      setSessions(res.data);
  
      // 4. 如果删除的是当前会话，切换到其他会话或创建新会话
      if (targetSessionId === sessionId) {
        const remaining = res.data.filter((s: Session) => s.id !== targetSessionId);
        if (remaining.length > 0) {
          await switchSessionRef.current?.(remaining[0].id);
        } else {
          await newChatRef.current?.();
        }
      }
    } catch (err: any) {
      console.error('Failed to delete session:', err);
      // 回滚乐观更新
      const res = await chatAPI.getSessions().catch(() => null);
      if (res) setSessions(res.data);
        
      if (err.response?.status === 401) {
        authFailedRef.current = true;
        return;
      }
        
      toast.error('删除会话失败');
    } finally {
      deletingRef.current = false;
    }
  }, [sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

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
        toolCalls: [],
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setLoading(true);
      updateThinking(true);  // 开始思考

      chatAPI.sendMessageStream(
        sessionId,
        content,
        // onToken
        (token: string) => {
          // ✅ 收到第一个 token 时停止 thinking（用 ref 避免闭包捕获旧值）
          if (isThinkingRef.current) {
            updateThinking(false);
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
          updateThinking(false);  // 确保 thinking 状态关闭
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
            updateThinking(false);
            return;
          }
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: '抱歉，发生了错误。请稍后重试。', isError: true }
                : m
            )
          );
          // ✅ 流失败且尚未产出任何回复时，保留草稿供用户重发
          const assistantContent =
            messagesRef.current.find((m) => m.id === assistantId)?.content ?? '';
          if (!assistantContent) {
            setPendingDraft(content);
            toast.error('消息发送失败，草稿已恢复到输入框');
          }
          setLoading(false);
          updateThinking(false);  // 确保 thinking 状态关闭
          abortRef.current = null;
        },
        controller.signal,
        // ✅ ui-redesign 决策 10/13：onToolStart/onToolEnd 按 id 配对消费结构化事件
        (payload) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    toolCalls: [
                      ...(m.toolCalls || []),
                      { id: payload.id, name: payload.name, args: payload.args, status: 'running' as const },
                    ],
                  }
                : m
            )
          );
        },
        (payload) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    // 孤儿 end（找不到配对 id）直接忽略，不新增行
                    toolCalls: (m.toolCalls || []).map((tc) =>
                      tc.id === payload.id
                        ? {
                            ...tc,
                            status: payload.status,
                            resultSummary: payload.resultSummary,
                            resultRaw: payload.resultRaw,
                            durationMs: payload.durationMs,
                          }
                        : tc
                    ),
                  }
                : m
            )
          );
        }
      );
    },
    [sessionId, loading]
  );

  // ── Cancel stream ──
  const cancelStream = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
    updateThinking(false);
    // ✅ ui-redesign 决策 13：cancelStream 时把当前仍在 running 的工具行批量转 stopped
    setMessages((prev) =>
      prev.map((m) =>
        m.toolCalls && m.toolCalls.some((tc) => tc.status === 'running')
          ? {
              ...m,
              toolCalls: m.toolCalls.map((tc) =>
                tc.status === 'running' ? { ...tc, status: 'stopped' as const } : tc
              ),
            }
          : m
      )
    );
  }, []);

  // ── New chat ──
  const newChat = useCallback(async () => {
    // Cancel any in-flight SSE
    abortRef.current?.abort();
    abortRef.current = null;

    setMessages([]);
    setLoading(false);
    restoredSessionRef.current = null;

    // ✅ 空会话复用：当前会话没有任何消息时直接复用，避免侧边栏堆积空"新对话"
    const currentId = localStorage.getItem('chat_session_id');
    if (currentId && messagesRef.current.length === 0) {
      await loadSessions();
      return;
    }

    const id = await createSession();
    if (id) {
      restoredSessionRef.current = id;
      // Refresh session list to include the new one
      await loadSessions();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  // ✅ 同步 ref，供 deleteSession 使用最新版本
  newChatRef.current = newChat;

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
        pendingDraft,
        clearPendingDraft,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}
