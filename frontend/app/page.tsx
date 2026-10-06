'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Briefcase, MessageSquare, User } from 'lucide-react'
import { buttonClasses } from '@/components/ui/Button'

export default function Home() {
  const router = useRouter()

  // Check if user is logged in
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (token) {
      // User is logged in, redirect to dashboard
      router.push('/dashboard')
    }
  }, [router])

  return (
    <main className="min-h-screen bg-base animate-fade-in">
      {/* Header Section — ui-redesign 决策 5.6：首屏改「一句话 + 直接开始」 */}
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-16 text-center">
        <div className="mx-auto h-16 w-16 bg-primary-500 rounded-dialog flex items-center justify-center mb-8">
          <svg className="h-9 w-9 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
        </div>

        {/* 品牌时刻保留：logo 场景的 gradient-text 是唯一豁免（决策 1.5） */}
        <h1 className="text-4xl font-medium gradient-text mb-4 tracking-tight">
          Intelli-Job
        </h1>
        <p className="text-lg text-700 mb-10">
          AI 驱动的智能求职助手，帮你找到理想工作
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link href="/login" className={buttonClasses('primary', 'md', 'px-8 text-base')}>
            直接开始
          </Link>
          <Link href="/register" className={buttonClasses('secondary', 'md', 'px-8 text-base')}>
            注册账号
          </Link>
        </div>
      </div>

      {/* Feature Cards — 降级为次级区块：去动画/发光/渐变，仅保留中性卡片与图标 */}
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pb-20">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Link href="/login"
                className="bg-layer1 border border-l1 rounded-menu shadow-lv1 p-6 hover:bg-hover-neutral transition-colors duration-base ease-ds">
            <Briefcase className="w-6 h-6 text-primary-500 mb-4" strokeWidth={1.5} />
            <h2 className="text-lg font-medium text-900 mb-2">职位匹配</h2>
            <p className="text-sm text-500 leading-relaxed">
              上传简历，AI 智能分析你的技能与经验，精准推荐最适合的岗位
            </p>
          </Link>

          <Link href="/chat"
                className="bg-layer1 border border-l1 rounded-menu shadow-lv1 p-6 hover:bg-hover-neutral transition-colors duration-base ease-ds">
            <MessageSquare className="w-6 h-6 text-primary-500 mb-4" strokeWidth={1.5} />
            <h2 className="text-lg font-medium text-900 mb-2">求职助手</h2>
            <p className="text-sm text-500 leading-relaxed">
              与 AI 对话，获取个性化求职建议、面试技巧和职业规划指导
            </p>
          </Link>

          <Link href="/profile"
                className="bg-layer1 border border-l1 rounded-menu shadow-lv1 p-6 hover:bg-hover-neutral transition-colors duration-base ease-ds">
            <User className="w-6 h-6 text-primary-500 mb-4" strokeWidth={1.5} />
            <h2 className="text-lg font-medium text-900 mb-2">我的画像</h2>
            <p className="text-sm text-500 leading-relaxed">
              管理你的技能树、求职偏好和个人档案，全面了解自己的竞争力
            </p>
          </Link>
        </div>
      </div>

      {/* Footer */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 border-t border-l1">
        <p className="text-500 text-sm text-center">
          © {new Date().getFullYear()} Intelli-Job. 基于 AI 技术的智能求职平台
        </p>
      </div>
    </main>
  )
}
