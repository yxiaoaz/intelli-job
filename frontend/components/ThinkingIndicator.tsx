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

  // ui-redesign 决策 6：思考态弱化为直排文本（无卡片/无玻璃态/无彩色发光），
  // 与去卡片化后的 AI 正文同轴对齐（32px 头像位 + 12px 间距）
  return (
    <div className="flex items-center gap-3 animate-fade-in">
      <div className="w-8 h-8 rounded-full bg-layer2 border border-l1 flex items-center justify-center flex-shrink-0">
        <Brain className="w-4 h-4 text-primary-500 animate-pulse" strokeWidth={1.5} />
      </div>

      {/* 动态文案 */}
      <span className="text-sm text-500 flex-1 transition-opacity duration-slow ease-ds">
        {phaseList[phaseIdx]}
      </span>

      {/* 加载点 */}
      <div className="loading-dots flex-shrink-0">
        <span></span>
        <span></span>
        <span></span>
      </div>
    </div>
  );
}
