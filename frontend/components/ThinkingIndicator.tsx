'use client';

import { Brain } from 'lucide-react';

interface ThinkingIndicatorProps {
  message?: string;
}

export default function ThinkingIndicator({ message = "模型正在思考..." }: ThinkingIndicatorProps) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 glass rounded-xl border border-primary-200/50 dark:border-primary-700/50 shadow-md animate-fade-in">
      {/* 动画图标 */}
      <div className="relative">
        <Brain className="w-6 h-6 text-primary-600 dark:text-primary-400 animate-pulse" />
        <div className="absolute inset-0 bg-primary-400/20 rounded-full animate-ping"></div>
      </div>

      {/* 文字 */}
      <div className="flex-1">
        <p className="text-sm font-medium text-gray-900 dark:text-white">{message}</p>
        <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
          AI 正在分析你的意图，请稍候...
        </p>
      </div>

      {/* 加载点 */}
      <div className="loading-dots">
        <span></span>
        <span></span>
        <span></span>
      </div>
    </div>
  );
}
