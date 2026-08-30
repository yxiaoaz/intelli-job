'use client';

import { useState, useEffect, useCallback } from 'react';
import { jobAPI } from '@/lib/api';
import { toast } from 'sonner';

/**
 * 统一收藏状态管理 hook
 *
 * - 挂载时从后端拉取用户收藏列表初始化状态，保证跨页面一致
 * - 同时构建 jobId → status 的 statusMap，供"已投递 ✓"等状态文案在刷新后保持
 *   （未登录或请求失败时静默保持空 map，与现有 catch 行为一致）
 * - toggleBookmark 处理 add/remove、409 归并、失败 toast
 * - markApplied 两步写（POST + PATCH status=applied）实现"标记已投递"
 * - onSync 回调供调用方同步自身数据（如 jobs state 的 is_bookmarked）
 */
export function useBookmark() {
  const [bookmarkedIds, setBookmarkedIds] = useState<Set<string>>(new Set());
  const [statusMap, setStatusMap] = useState<Map<string, string>>(new Map());

  // 初始化：拉取用户收藏列表，顺带构建 statusMap（零额外请求）
  useEffect(() => {
    let cancelled = false;
    jobAPI.bookmarks
      .getList()
      .then((res) => {
        if (cancelled) return;
        const list = res.data || [];
        setBookmarkedIds(new Set(list.map((b: any) => String(b.job_id))));
        const map = new Map<string, string>();
        for (const b of list) {
          map.set(String(b.job_id), b.status);
        }
        setStatusMap(map);
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

  /** 读取职位当前申请状态；未收藏或未知时返回 null */
  const getStatus = useCallback(
    (jobId: string) => statusMap.get(String(jobId)) ?? null,
    [statusMap]
  );

  const setStatus = useCallback((jobId: string, status: string) => {
    setStatusMap((prev) => {
      const next = new Map(prev);
      next.set(String(jobId), status);
      return next;
    });
  }, []);

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
          // 同步移除状态记录
          setStatusMap((prev) => {
            const next = new Map(prev);
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

  /**
   * 标记已投递：未收藏先 POST 收藏再 PATCH status=applied；已收藏直接 PATCH。
   * PATCH 失败但收藏已成功时，引导用户到求职看板补标状态。
   */
  const markApplied = useCallback(
    async (jobId: string, onSync?: (jobId: string, newState: boolean) => void) => {
      const id = String(jobId);
      let addedHere = false; // 本次调用是否新创建了收藏

      if (!bookmarkedIds.has(id)) {
        try {
          await jobAPI.bookmarks.add(id);
          setBookmarkedIds((prev) => new Set(prev).add(id));
          onSync?.(id, true);
          addedHere = true;
        } catch (error: any) {
          if (error?.response?.status === 409) {
            // 后端已收藏，视为已收藏继续 PATCH
            setBookmarkedIds((prev) => new Set(prev).add(id));
            onSync?.(id, true);
          } else {
            toast.error('操作失败，请重试');
            return;
          }
        }
      }

      try {
        await jobAPI.bookmarks.update(id, { status: 'applied' });
        setStatus(id, 'applied');
        toast.success('已标记为已投递');
      } catch {
        if (addedHere) {
          // 收藏已成功，只差状态一步
          toast.error('已收藏，请到求职看板标记投递状态');
        } else {
          toast.error('状态更新失败，请重试');
        }
      }
    },
    [bookmarkedIds, setStatus]
  );

  return { bookmarkedIds, isBookmarked, getStatus, statusMap, toggleBookmark, markApplied };
}
