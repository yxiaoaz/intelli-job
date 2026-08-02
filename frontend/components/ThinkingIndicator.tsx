'use client';

import { useState, useEffect } from 'react';
import { Brain } from 'lucide-react';

interface ThinkingIndicatorProps {
  phases?: string[];
}

const DEFAULT_PHASES = [
  '正在读取你的简历...',
  '正在分析岗位要求...',
  '正在比较匹配度...',
];

export default function ThinkingIndicator({ phases }: ThinkingIndicatorProps) {
  const phaseList = phases ?? DEFAULT_PHASES;
  const [phaseIdx, setPhaseIdx] = useState(0);

  useEffect(() => {
    if (phaseList.length <= 1) return;
    const timer = setInterval(() => {
      setPhaseIdx((prev) => (prev + 1) % phaseList.length);
    }, 1500);
    return () => clearInterval(timer);
  }, [phaseList.length]);

  return (
    <div className="flex items-center gap-3 px-4 py-3 glass rounded-xl border border-primary-200/50 dark:border-primary-700/50 shadow-md animate-fade-in max-w-[280px]">
      {/* 动画图标 */}
      <div className="relative flex-shrink-0">
        <Brain className="w-5 h-5 text-primary-600 dark:text-primary-400 animate-pulse" />
      </div>

      {/* 动态文案 */}
      <span className="text-sm text-gray-600 dark:text-gray-400 flex-1 transition-opacity duration-300">
        {phaseList[phaseIdx]}
      </span>

      {/* 加载点 */}
      <div className="flex gap-1 flex-shrink-0">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-primary-500 dark:bg-primary-400 animate-pulse"
            style={{ animationDelay: `${i * 0.2}s` }}
          />
        ))}
      </div>
    </div>
  );
}
