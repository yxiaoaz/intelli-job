'use client';

import { useState, useEffect, useCallback } from 'react';
import { jobAPI } from '@/lib/api';
import { toast } from 'sonner';

/**
 * 统一收藏状态管理 hook
 *
 * - 挂载时从后端拉取用户收藏列表初始化状态，保证跨页面一致
 * - toggleBookmark 处理 add/remove、409 归并、失败 toast
 * - onSync 回调供调用方同步自身数据（如 jobs state 的 is_bookmarked）
 */
export function useBookmark() {
  const [bookmarkedIds, setBookmarkedIds] = useState<Set<string>>(new Set());

  // 初始化：拉取用户收藏列表
  useEffect(() => {
    let cancelled = false;
    jobAPI.bookmarks
      .getList()
      .then((res) => {
        if (cancelled) return;
        const ids = (res.data || []).map((b: any) => String(b.job_id));
        setBookmarkedIds(new Set(ids));
      })
      .catch(() => {
        // 未登录或接口失败时保持空集合，不阻塞页面
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const isBookmarked = useCallback(
    (jobId: string) => bookmarkedIds.has(String(jobId)),
    [bookmarkedIds]
  );

  const toggleBookmark = useCallback(
    async (jobId: string, onSync?: (jobId: string, newState: boolean) => void) => {
      const id = String(jobId);
      const wasBookmarked = bookmarkedIds.has(id);
      try {
        if (wasBookmarked) {
          await jobAPI.bookmarks.remove(id);
          setBookmarkedIds((prev) => {
            const next = new Set(prev);
            next.delete(id);
            return next;
          });
          onSync?.(id, false);
          toast.success('已取消收藏');
        } else {
          await jobAPI.bookmarks.add(id);
          setBookmarkedIds((prev) => new Set(prev).add(id));
          onSync?.(id, true);
          toast.success('已收藏');
        }
      } catch (error: any) {
        if (error?.response?.status === 409) {
          // 后端已存在收藏，同步为已收藏状态
          setBookmarkedIds((prev) => new Set(prev).add(id));
          onSync?.(id, true);
        } else {
          toast.error('操作失败，请重试');
        }
      }
    },
    [bookmarkedIds]
  );

  return { bookmarkedIds, isBookmarked, toggleBookmark };
}
