'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
import { jobAPI } from '@/lib/api';
import { formatMonthDay } from '@/lib/time';
import { toast } from 'sonner';
import { ExternalLink, Bookmark, Loader2, Briefcase } from 'lucide-react';
import { buttonClasses } from '@/components/ui/Button';

// ---------- 状态常量（与后端 ApplicationStatus 枚举一致） ----------
const STATUS_OPTIONS = [
  { value: 'saved', label: '已收藏' },
  { value: 'applied', label: '已投递' },
  { value: 'interviewing', label: '面试中' },
  { value: 'rejected', label: '已拒绝' },
  { value: 'accepted', label: '已录用' },
] as const;

type BookmarkStatus = (typeof STATUS_OPTIONS)[number]['value'];

// 状态色（design 约定：saved 灰 / applied 蓝 / interviewing 琥珀 / rejected 红 / accepted 青绿）
const STATUS_STYLE: Record<BookmarkStatus, { dot: string }> = {
  saved: { dot: 'bg-layer2' },
  applied: { dot: 'bg-tint-primary' },
  interviewing: { dot: 'bg-tint-warning' },
  rejected: { dot: 'bg-tint-danger' },
  accepted: { dot: 'bg-tint-primary' },
};

// ---------- 类型 ----------
interface BookmarkItem {
  id: string;
  job_id: string;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string | null;
  job: {
    id: string;
    title: string;
    company: string;
    location: string;
    salary: string;
    recruitment_type?: string;
    url?: string;
  };
}

export default function BookmarksPage() {
  const router = useRouter();

  const [bookmarks, setBookmarks] = useState<BookmarkItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'all' | BookmarkStatus>('all');
  // 备注编辑态：正在编辑的 bookmark id -> 草稿文本
  const [editingNotes, setEditingNotes] = useState<Record<string, string>>({});

  // 认证检查（与其他页一致）
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/login');
    }
  }, [router]);

  // 加载全量收藏
  useEffect(() => {
    let cancelled = false;
    jobAPI.bookmarks
      .getList()
      .then((res) => {
        if (cancelled) return;
        setBookmarks(res.data || []);
      })
      .catch(() => {
        if (!cancelled) toast.error('加载收藏列表失败，请刷新重试');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // 漏斗四格计数（前端从全量列表计算；rejected 不计入漏斗）
  const funnel = useMemo(() => {
    const counts = { saved: 0, applied: 0, interviewing: 0, accepted: 0 };
    for (const b of bookmarks) {
      if (b.status in counts) {
        counts[b.status as keyof typeof counts] += 1;
      }
    }
    return counts;
  }, [bookmarks]);

  // 各状态 tab 计数（含 rejected）
  const tabCounts = useMemo(() => {
    const counts: Record<string, number> = { all: bookmarks.length };
    for (const b of bookmarks) {
      counts[b.status] = (counts[b.status] || 0) + 1;
    }
    return counts;
  }, [bookmarks]);

  const filtered =
    activeTab === 'all' ? bookmarks : bookmarks.filter((b) => b.status === activeTab);

  // ---------- 交互 ----------

  /** 状态下拉：乐观更新 + PATCH，失败回滚 + toast */
  const handleStatusChange = useCallback(
    async (bookmark: BookmarkItem, nextStatus: BookmarkStatus) => {
      const prevStatus = bookmark.status;
      if (prevStatus === nextStatus) return;

      // 乐观更新
      setBookmarks((prev) =>
        prev.map((b) =>
          b.job_id === bookmark.job_id ? { ...b, status: nextStatus } : b
        )
      );
      try {
        const res = await jobAPI.bookmarks.update(bookmark.job_id, {
          status: nextStatus,
        });
        // 以后端返回为准（updated_at 等）
        setBookmarks((prev) =>
          prev.map((b) => (b.job_id === bookmark.job_id ? { ...b, ...res.data } : b))
        );
      } catch {
        // 回滚
        setBookmarks((prev) =>
          prev.map((b) =>
            b.job_id === bookmark.job_id ? { ...b, status: prevStatus } : b
          )
        );
        toast.error('状态更新失败，请重试');
      }
    },
    []
  );

  /** 保存备注：PATCH {notes}，空串表示清空 */
  const handleSaveNotes = useCallback(async (bookmark: BookmarkItem) => {
    const draft = editingNotes[bookmark.id];
    if (draft === undefined) return;
    try {
      const res = await jobAPI.bookmarks.update(bookmark.job_id, {
        notes: draft,
      });
      setBookmarks((prev) =>
        prev.map((b) => (b.job_id === bookmark.job_id ? { ...b, ...res.data } : b))
      );
      setEditingNotes((prev) => {
        const next = { ...prev };
        delete next[bookmark.id];
        return next;
      });
      toast.success(draft === '' ? '备注已清空' : '备注已保存');
    } catch {
      toast.error('备注保存失败，请重试');
    }
  }, [editingNotes]);

  const timelineText = (b: BookmarkItem) => {
    if (b.status === 'saved') {
      return `收藏于 ${formatMonthDay(b.created_at)}`;
    }
    return `${formatMonthDay(b.updated_at || b.created_at)} 更新`;
  };

  return (
    <div className="min-h-screen bg-layer1">
      <Navbar currentPath="/bookmarks" />

      <main className="max-w-5xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-medium text-900 mb-6">
          求职看板
        </h1>

        {loading ? (
          <div className="flex items-center justify-center py-20 text-500">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            加载中...
          </div>
        ) : bookmarks.length === 0 ? (
          /* 空状态：引导去职位搜索 */
          <div className="flex flex-col items-center justify-center py-20">
            <Bookmark className="w-16 h-16 text-400 mb-4" />
            <p className="text-500 mb-6">
              还没有收藏职位，去职位搜索找到心仪岗位吧
            </p>
            <button
              onClick={() => router.push('/dashboard')}
              className={buttonClasses('primary', 'md', 'mx-auto')}
            >
              <Briefcase className="w-4 h-4" />
              去职位搜索
            </button>
          </div>
        ) : (
          <>
            {/* 漏斗条 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
              {(
                [
                  { key: 'saved', label: '已收藏' },
                  { key: 'applied', label: '已投递' },
                  { key: 'interviewing', label: '面试中' },
                  { key: 'accepted', label: 'Offer' },
                ] as const
              ).map(({ key, label }) => (
                <div
                  key={key}
                  className="bg-base rounded-menu border border-l2 p-4"
                >
                  <div className={`text-2xl font-medium ${STATUS_STYLE[key].dot.replace('bg-', 'text-')}`}>
                    {funnel[key]}
                  </div>
                  <div className="text-xs text-500 mt-1">{label}</div>
                </div>
              ))}
            </div>

            {/* 状态 Tab */}
            <div className="flex flex-wrap gap-2 mb-6">
              {(
                [
                  { value: 'all', label: '全部' },
                  ...STATUS_OPTIONS,
                ] as { value: 'all' | BookmarkStatus; label: string }[]
              ).map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => setActiveTab(value)}
                  className={`px-3 py-1.5 rounded-btn text-sm font-medium transition-colors ${
                    activeTab === value
                      ? 'bg-tint-primary text-tint-primary'
                      : 'bg-base text-700 border border-l1 hover:border-l2 hover:bg-hover-neutral'
                  }`}
                >
                  {label}
                  <span className="ml-1 text-xs opacity-80">{tabCounts[value] || 0}</span>
                </button>
              ))}
            </div>

            {/* 收藏卡片列表 */}
            <div className="space-y-4">
              {filtered.map((b) => {
                const isEditingNotes = editingNotes[b.id] !== undefined;
                return (
                  <div
                    key={b.id}
                    className={`
                      bg-base rounded-menu border p-4 transition-colors
                      ${
                        b.status === 'rejected'
                          ? 'border-l2 opacity-60'
                          : b.status === 'accepted'
                            ? 'border-tint-primary ring-1 ring-primary-200'
                            : 'border-l2'
                      }
                    `}
                  >
                    {/* 第一行：标题 + 状态下拉 + 去源站 */}
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <h3 className="text-base font-medium text-900 truncate">
                          {b.job.title}
                        </h3>
                        <p className="text-sm text-500 mt-1">
                          {b.job.company} · {b.job.location || '未指定'} · {timelineText(b)}
                        </p>
                      </div>

                      <div className="flex items-center gap-2 flex-shrink-0">
                        {/* 状态下拉：改动即 PATCH */}
                        <select
                          value={b.status}
                          onChange={(e) =>
                            handleStatusChange(b, e.target.value as BookmarkStatus)
                          }
                          onClick={(e) => e.stopPropagation()}
                          className={`text-xs font-medium rounded-input border border-l2
                                     px-2 py-1.5 bg-base cursor-pointer
                                     focus:outline-none focus:ring-2 focus:ring-primary-200/40`}
                          aria-label="申请状态"
                        >
                          {STATUS_OPTIONS.map((s) => (
                            <option key={s.value} value={s.value}>
                              {s.label}
                            </option>
                          ))}
                        </select>

                        {/* 去源站外链 */}
                        {b.job.url && (
                          <button
                            onClick={() => window.open(b.job.url, '_blank')}
                            className="px-2 py-1.5 text-xs rounded-menu text-500
                                       hover:text-tint-primary
                                       transition-colors flex items-center gap-1"
                            title="跳转到源站投递"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            去源站
                          </button>
                        )}
                      </div>
                    </div>

                    {/* 备注区 */}
                    {isEditingNotes ? (
                      <div className="mt-3">
                        <textarea
                          value={editingNotes[b.id]}
                          onChange={(e) =>
                            setEditingNotes((prev) => ({
                              ...prev,
                              [b.id]: e.target.value,
                            }))
                          }
                          rows={3}
                          maxLength={2000}
                          placeholder="记录投递进展、内推人、面试反馈等（留空保存即清空）"
                          className="w-full text-sm rounded-input border border-l2
                                     bg-layer1 px-3 py-2 text-700
                                     focus:outline-none focus:ring-2 focus:ring-primary-200/40 resize-y"
                        />
                        <div className="flex justify-end gap-2 mt-2">
                          <button
                            onClick={() =>
                              setEditingNotes((prev) => {
                                const next = { ...prev };
                                delete next[b.id];
                                return next;
                              })
                            }
                            className={buttonClasses('secondary', 'sm')}
                          >
                            取消
                          </button>
                          <button
                            onClick={() => handleSaveNotes(b)}
                            className={buttonClasses('primary', 'sm')}
                          >
                            保存
                          </button>
                        </div>
                      </div>
                    ) : (
                      b.notes && (
                        <div className="mt-3 flex items-start justify-between gap-3 bg-layer1 rounded-menu px-3 py-2">
                          <p className="text-sm text-700 whitespace-pre-wrap break-words">
                            <span className="text-400">备注：</span>
                            {b.notes}
                          </p>
                          <button
                            onClick={() => setEditingNotes((prev) => ({ ...prev, [b.id]: b.notes || '' }))}
                            className="flex-shrink-0 text-xs text-tint-primary
                                       hover:text-tint-primary transition-colors"
                          >
                            编辑
                          </button>
                        </div>
                      )
                    )}
                  </div>
                );
              })}

              {filtered.length === 0 && (
                <div className="text-center py-12 text-500 text-sm">
                  该状态下暂无职位
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
