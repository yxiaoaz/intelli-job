'use client';

/**
 * ui-redesign 决策 12：渲染器下沉注册表。
 *
 * 每个工具自带 args/result 摘要函数与图标，ChatMessage 侧的 ToolRow 只需按
 * name 查这张表即可渲染，不再散落 if/else 判断工具名。未注册的工具走
 * GenericToolView 兜底（Sparkle 图标 + name 原文）。
 *
 * 时态文案（"正在{label}…"/"已{label}"）在本层统一拼接，收敛决策 11 的
 * "文案时态收敛到前端"要求——后端 TOOL_ACTION_LABELS 只下发中性短语。
 */

import {
  Search,
  User,
  FileText,
  FilePen,
  FolderOpen,
  Save,
  Target,
  Sparkle,
} from 'lucide-react';
import type { ReactNode } from 'react';

export interface ToolView {
  icon: ReactNode;
  /** 中性动作短语，对应后端 TOOL_ACTION_LABELS（决策 11），running/ok 复用 */
  title: string;
  /** 完成态标题覆写（不规则短语，如"已搜索岗位"而非机械拼接的"已搜索匹配岗位"时用） */
  titleDone?: string;
  /** 单行参数摘要，running 态使用；防御式取值，args 结构不固定也不抛错 */
  summarizeArgs?: (args: unknown) => string;
  /** 单行结果摘要，用于无 tool_events 降级渲染时按原始结果文本兜底计算 */
  summarizeResult?: (result: string) => string;
  /** 是否参与连续同类调用的分组合并（决策 14） */
  groupable?: boolean;
  /** 覆写展开详情面板的输出段（如 search_jobs 用岗位列表替代原始 JSON） */
  renderDetail?: (args: unknown, resultRaw: string) => ReactNode;
}

const ARGS_TRUNCATE_AT = 60;

function truncate(s: string, at = ARGS_TRUNCATE_AT): string {
  return s.length > at ? `${s.slice(0, at)}…` : s;
}

/** 决策 12：summarizeArgs 防御式取值——string 直截断 / object 取首个标量字段 */
export function defensiveFirstScalar(args: unknown): string {
  if (typeof args === 'string') return truncate(args);
  if (args && typeof args === 'object') {
    for (const v of Object.values(args as Record<string, unknown>)) {
      if (typeof v === 'string' && v) return truncate(v);
      if (typeof v === 'number') return truncate(String(v));
    }
  }
  return '';
}

const searchJobsView: ToolView = {
  icon: <Search className="w-4 h-4" strokeWidth={1.5} />,
  title: '搜索匹配岗位',
  groupable: false,
  summarizeArgs: (args) => {
    const a = (args || {}) as { location?: string; role?: string; keyword?: string; keywords?: string };
    return [a.location, a.role, a.keyword || a.keywords].filter(Boolean).join(' · ');
  },
  summarizeResult: (result) => {
    try {
      const parsed = JSON.parse(result);
      const jobs = Array.isArray(parsed?.jobs) ? parsed.jobs : [];
      return `找到 ${jobs.length} 个岗位`;
    } catch {
      return truncate(result, 80);
    }
  },
  renderDetail: (_args, resultRaw) => {
    try {
      const parsed = JSON.parse(resultRaw);
      const jobs: Array<{ title?: string; company?: string }> = Array.isArray(parsed?.jobs) ? parsed.jobs : [];
      const top3 = jobs.slice(0, 3);
      if (top3.length === 0) return <span className="text-500">未命中岗位</span>;
      return (
        <ul className="space-y-1">
          {top3.map((j, i) => (
            <li key={i} className="text-700">
              {j.title || '未知岗位'} · {j.company || '未知公司'}
            </li>
          ))}
        </ul>
      );
    } catch {
      return null; // 调用方回退到默认 head+tail 渲染
    }
  },
};

const getUserProfileView: ToolView = {
  icon: <User className="w-4 h-4" strokeWidth={1.5} />,
  title: '查阅用户画像',
  groupable: true,
  summarizeResult: (result) => truncate(result, 80),
};

const readFileView: ToolView = {
  icon: <FileText className="w-4 h-4" strokeWidth={1.5} />,
  title: '读取记忆文件',
  groupable: true,
  summarizeArgs: (args) => {
    const a = (args || {}) as { file_path?: string };
    return a.file_path ? truncate(a.file_path) : '';
  },
  summarizeResult: (result) => {
    const firstLine = result.split('\n')[0]?.trim();
    return firstLine ? truncate(firstLine, 80) : `${result.length} 字符`;
  },
};

const writeFileView: ToolView = {
  icon: <FilePen className="w-4 h-4" strokeWidth={1.5} />,
  title: '更新记忆文件',
  groupable: true,
  summarizeArgs: (args) => {
    const a = (args || {}) as { file_path?: string };
    return a.file_path ? truncate(a.file_path) : '';
  },
  summarizeResult: (result) => {
    const lines = result.split('\n').length;
    return lines > 1 ? `${lines} 行变更` : `${result.length} 字符`;
  },
};

const lsView: ToolView = {
  icon: <FolderOpen className="w-4 h-4" strokeWidth={1.5} />,
  title: '浏览文件目录',
  groupable: true,
  summarizeArgs: (args) => defensiveFirstScalar(args),
  summarizeResult: (result) => truncate(result, 80),
};

const updateMemoryView: ToolView = {
  icon: <Save className="w-4 h-4" strokeWidth={1.5} />,
  title: '更新偏好档案',
  groupable: true,
  summarizeArgs: (args) => defensiveFirstScalar(args),
  summarizeResult: (result) => truncate(result, 80),
};

const analyzeJobMatchView: ToolView = {
  icon: <Target className="w-4 h-4" strokeWidth={1.5} />,
  title: '分析岗位匹配',
  groupable: false,
  summarizeArgs: (args) => defensiveFirstScalar(args),
  summarizeResult: (result) => truncate(result, 80),
};

const REGISTRY: Record<string, ToolView> = {
  search_jobs: searchJobsView,
  get_user_profile: getUserProfileView,
  read_file: readFileView,
  write_file: writeFileView,
  edit_file: writeFileView,
  ls: lsView,
  update_session_memory: updateMemoryView,
  update_user_memory: updateMemoryView,
  analyze_job_match: analyzeJobMatchView,
};

/** 未注册工具兜底（决策 12）：Sparkle 图标 + name 原文 */
export const GenericToolView: ToolView = {
  icon: <Sparkle className="w-4 h-4" strokeWidth={1.5} />,
  title: '处理你的请求',
  groupable: true,
  summarizeArgs: (args) => defensiveFirstScalar(args),
  summarizeResult: (result) => truncate(result.split('\n')[0] || result, 80),
};

export function getToolView(name: string): ToolView {
  return REGISTRY[name] || GenericToolView;
}

/** running 态文案：正在{label}… */
export function runningLabel(view: ToolView): string {
  return `正在${view.title}…`;
}

/** ok 态文案：已{label}；不规则短语在 registry 用 titleDone 覆写 */
export function doneLabel(view: ToolView): string {
  return view.titleDone ? `已${view.titleDone}` : `已${view.title}`;
}
