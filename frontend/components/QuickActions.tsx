'use client';

import { FileUp, Search, MapPin } from 'lucide-react';

interface QuickActionsProps {
  jobs: any[];
  onAction: (actionText: string) => void;
}

/** Extract primary city from location string */
function extractCity(location: string): string {
  if (!location) return '';
  return location.split('/')[0]?.trim() || '';
}

/** Extract direction hints from job titles */
function extractDirections(jobs: any[]): string[] {
  const keywords = new Set<string>();
  const patterns = [
    /C端/, /B端/, /策略/, /平台/, /音视频/, /数据/,
    /增长/, /商业化/, /推荐/, /算法/, /前端/, /后端/,
    /产品/, /运营/, /设计/,
  ];

  jobs.forEach((j: any) => {
    const title: string = j.title || '';
    patterns.forEach((p) => {
      const match = title.match(p);
      if (match) keywords.add(match[0]);
    });
  });

  return Array.from(keywords).slice(0, 3);
}

export default function QuickActions({ jobs, onAction }: QuickActionsProps) {
  if (!jobs || jobs.length === 0) return null;

  const maxScore = Math.max(...jobs.map((j) => j.match_score ?? 0), 0);
  const directions = extractDirections(jobs);

  // Collect cities NOT in the current results for "switch city" suggestions
  const currentCities = new Set(jobs.map((j) => extractCity(j.location)).filter(Boolean));
  // Suggest popular job cities that aren't already in results
  const popularCities = ['北京', '上海', '深圳', '广州', '杭州', '成都'];
  const otherCities = popularCities.filter((c) => !currentCities.has(c)).slice(0, 2);

  const actions: { icon: React.ReactNode; label: string; text: string }[] = [];

  // Low match → suggest resume upload
  if (maxScore < 10) {
    actions.push({
      icon: <FileUp className="w-3.5 h-3.5" />,
      label: '上传简历提升匹配度',
      text: '我想上传简历，帮我做更精准的匹配',
    });
  }

  // Direction-based search refinement
  if (directions.length > 0) {
    actions.push({
      icon: <Search className="w-3.5 h-3.5" />,
      label: `按${directions[0]}方向再搜`,
      text: `帮我找${directions[0]}方向的工作`,
    });
  }

  // City-based switch
  if (otherCities.length > 0) {
    const city = otherCities[0];
    actions.push({
      icon: <MapPin className="w-3.5 h-3.5" />,
      label: `换${city}看看`,
      text: `帮我看看${city}有什么合适的岗位`,
    });
  }

  if (actions.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {actions.map((action, idx) => (
        <button
          key={idx}
          onClick={() => onAction(action.text)}
          className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium
                     rounded-full border border-gray-200 dark:border-dark-500
                     bg-gray-100 dark:bg-dark-600 text-gray-700 dark:text-gray-300
                     hover:bg-primary-50 dark:hover:bg-dark-500
                     hover:border-primary-300 dark:hover:border-primary-600
                     hover:text-primary-700 dark:hover:text-primary-400
                     transition-all duration-150"
        >
          {action.icon}
          {action.label}
        </button>
      ))}
    </div>
  );
}
