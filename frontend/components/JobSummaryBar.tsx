'use client';

import { MapPin, Database, Sparkles, AlertTriangle } from 'lucide-react';

interface JobSummaryBarProps {
  jobs: any[];
}

/** Extract primary city from location string，兼容"北京/北京/海淀区"、"浙江省杭州市余杭区…"与"广州,杭州,"多种格式 */
function normalizeCity(part: string): string {
  const cleaned = part.replace(/^.*?(?:省|自治区)/, '');
  const cityMatch = cleaned.match(/^[^市]*?市/);
  if (cityMatch) return cityMatch[0].replace(/市$/, '');
  const municipality = cleaned.match(/^(北京|上海|天津|重庆)/);
  if (municipality) return municipality[1];
  // 无行政区划后缀且过长（如"邮编：311121"）不是城市名，丢弃
  if (cleaned.length > 4 && !/[州市区县]$/.test(cleaned)) return '';
  return cleaned;
}

function extractCities(location: string): string[] {
  if (!location) return [];
  // 斜杠格式（省/市/区）取中间的市级
  if (location.includes('/')) {
    const parts = location.split('/').filter(Boolean);
    const city = parts.length >= 2 ? parts[1] : parts[0];
    const normalized = normalizeCity(city.trim());
    return normalized ? [normalized] : [];
  }
  // 逗号分隔的多城市（可能带尾逗号），逐个归一后分别计数
  return location
    .split(/[,，]/)
    .map((p) => normalizeCity(p.trim()))
    .filter(Boolean);
}

/** Simplify source name: "Shixiseng | 实习僧" → "实习僧" */
function simplifySource(source: string): string {
  if (!source) return '未知';
  // Take the last part after " | " if exists
  const parts = source.split('|');
  return parts[parts.length - 1]?.trim() || source;
}

export default function JobSummaryBar({ jobs }: JobSummaryBarProps) {
  if (!jobs || jobs.length === 0) return null;

  // ── Compute stats ──
  const total = jobs.length;

  // City distribution（一个岗位可覆盖多城市，如"广州,杭州"）
  const cityMap = new Map<string, number>();
  jobs.forEach((j) => {
    for (const city of extractCities(j.location)) {
      cityMap.set(city, (cityMap.get(city) || 0) + 1);
    }
  });
  const citySummary = Array.from(cityMap.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([city, count]) => `${count}个${city}`)
    .join('、');

  // Source distribution
  const sourceMap = new Map<string, number>();
  jobs.forEach((j) => {
    const src = simplifySource(j.source);
    sourceMap.set(src, (sourceMap.get(src) || 0) + 1);
  });
  const sourceSummary = Array.from(sourceMap.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([src, count]) => `${src} × ${count}`)
    .join('、');

  // Match score range（✅ 无有效简历匹配时（<10）不渲染伪区间如"1-1%"）
  const scores = jobs
    .map((j) => j.match_score)
    .filter((s): s is number => typeof s === 'number' && s >= 10);
  const maxScore = scores.length > 0 ? Math.max(...scores) : 0;
  const minScore = scores.length > 0 ? Math.min(...scores) : 0;
  const hasValidScores = scores.length > 0;
  const isLowMatch = !hasValidScores;

  // Score color
  const scoreColor = maxScore >= 70
    ? 'text-green-600 dark:text-green-400'
    : maxScore >= 30
    ? 'text-orange-600 dark:text-orange-400'
    : 'text-red-600 dark:text-red-400';

  return (
    <div className="glass rounded-xl border border-primary-200/50 dark:border-primary-700/50 p-4">
      {/* Main stats row */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        {/* Total count */}
        <div className="flex items-center gap-1.5 font-semibold text-gray-900 dark:text-white">
          <Sparkles className="w-4 h-4 text-primary-500" />
          <span>找到 {total} 个岗位</span>
        </div>

        {/* Separator */}
        <span className="text-gray-300 dark:text-gray-600 hidden sm:inline">·</span>

        {/* City distribution */}
        <div className="flex items-center gap-1 text-gray-600 dark:text-gray-400">
          <MapPin className="w-3.5 h-3.5" />
          <span>{citySummary}</span>
        </div>

        {/* Separator */}
        <span className="text-gray-300 dark:text-gray-600 hidden sm:inline">·</span>

        {/* Source distribution */}
        <div className="flex items-center gap-1 text-gray-600 dark:text-gray-400">
          <Database className="w-3.5 h-3.5" />
          <span>来源: {sourceSummary}</span>
        </div>

        {/* Match score（无有效数据时不渲染） */}
        {hasValidScores && (
          <>
            {/* Separator */}
            <span className="text-gray-300 dark:text-gray-600 hidden sm:inline">·</span>

            <div className={`flex items-center gap-1 font-medium ${scoreColor}`}>
              <span>匹配度 {minScore.toFixed(0)}-{maxScore.toFixed(0)}%</span>
            </div>
          </>
        )}
      </div>

      {/* Low match warning */}
      {isLowMatch && (
        <div className="mt-3 flex items-start gap-2 px-3 py-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
          <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-amber-800 dark:text-amber-300 leading-relaxed">
            暂时无法评估匹配度，建议<strong>上传简历</strong>提升匹配精准度，或指定更具体的岗位方向
          </p>
        </div>
      )}
    </div>
  );
}
