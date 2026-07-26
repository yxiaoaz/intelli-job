'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Briefcase, MessageSquare, User } from 'lucide-react'

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
    <main className="min-h-screen bg-gradient-to-br from-dark-50 via-white to-primary-50 dark:from-dark-900 dark:via-dark-800 dark:to-dark-900 animate-fade-in">
      {/* Header Section */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-16">
        <div className="text-center">
          {/* Logo - 科技感增强 */}
          <div className="mx-auto h-24 w-24 bg-gradient-to-br from-primary-500 via-accent-cyan to-primary-600 rounded-3xl flex items-center justify-center shadow-glow-lg mb-10 transform hover:scale-110 transition-all duration-300 animate-pulse-slow">
            <svg className="h-14 w-14 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          
          {/* Title - 渐变文字效果 */}
          <h1 className="text-6xl md:text-7xl font-bold gradient-text mb-6 font-display tracking-tight">
            Intelli-Job
          </h1>
          <p className="text-xl md:text-2xl text-gray-700 dark:text-gray-300 max-w-3xl mx-auto mb-16 leading-relaxed">
            AI 驱动的智能求职助手，帮你找到理想工作
          </p>
        </div>

        {/* Feature Cards - 玻璃态设计 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto mb-20">
          <Link href="/login" 
                className="group relative glass rounded-3xl p-8 shadow-lg hover:shadow-glow-lg
                           border border-primary-200/50 dark:border-primary-700/50 transition-all duration-300 transform hover:-translate-y-2 card-hover">
            <div className="absolute inset-0 bg-gradient-to-br from-primary-500/10 to-accent-cyan/10 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            <div className="relative">
              <div className="w-16 h-16 bg-gradient-to-br from-primary-500 to-primary-600 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300 shadow-lg">
                <Briefcase className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-3 font-display">职位匹配</h2>
              <p className="text-gray-600 dark:text-gray-300 leading-relaxed">
                上传简历，AI 智能分析你的技能与经验，精准推荐最适合的岗位
              </p>
            </div>
          </Link>
          
          <Link href="/chat" 
                className="group relative glass rounded-3xl p-8 shadow-lg hover:shadow-glow-lg
                           border border-primary-200/50 dark:border-primary-700/50 transition-all duration-300 transform hover:-translate-y-2 card-hover">
            <div className="absolute inset-0 bg-gradient-to-br from-accent-cyan/10 to-primary-500/10 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            <div className="relative">
              <div className="w-16 h-16 bg-gradient-to-br from-accent-cyan to-accent-teal rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300 shadow-lg">
                <MessageSquare className="w-8 h-8 text-dark-900" />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-3 font-display">求职助手</h2>
              <p className="text-gray-600 dark:text-gray-300 leading-relaxed">
                与 AI 对话，获取个性化求职建议、面试技巧和职业规划指导
              </p>
            </div>
          </Link>
          
          <Link href="/profile" 
                className="group relative glass rounded-3xl p-8 shadow-lg hover:shadow-glow-lg
                           border border-primary-200/50 dark:border-primary-700/50 transition-all duration-300 transform hover:-translate-y-2 card-hover">
            <div className="absolute inset-0 bg-gradient-to-br from-primary-600/10 to-accent-cyan/10 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            <div className="relative">
              <div className="w-16 h-16 bg-gradient-to-br from-primary-600 to-primary-700 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300 shadow-lg">
                <User className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-3 font-display">我的画像</h2>
              <p className="text-gray-600 dark:text-gray-300 leading-relaxed">
                管理你的技能树、求职偏好和个人档案，全面了解自己的竞争力
              </p>
            </div>
          </Link>
        </div>

        {/* CTA Buttons - 强调按钮 */}
        <div className="text-center">
          <p className="text-gray-700 dark:text-gray-300 mb-8 text-lg">
            准备好开始你的求职之旅了吗？
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link 
              href="/login" 
              className="inline-flex items-center justify-center px-10 py-4 bg-gradient-to-r from-primary-600 via-primary-500 to-accent-cyan
                         hover:from-primary-700 hover:via-primary-600 hover:to-accent-teal text-white font-bold rounded-2xl shadow-glow-lg hover:shadow-glow
                         transition-all duration-200 transform hover:scale-105 active:scale-95 text-lg"
            >
              <svg className="w-6 h-6 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
              </svg>
              立即登录
            </Link>
            <Link 
              href="/register" 
              className="inline-flex items-center justify-center px-10 py-4 bg-white dark:bg-dark-700
                         border-2 border-primary-500 dark:border-primary-400 text-primary-600 dark:text-primary-400
                         font-bold rounded-2xl hover:bg-primary-50 dark:hover:bg-dark-600
                         transition-all duration-200 transform hover:scale-105 active:scale-95 text-lg"
            >
              <svg className="w-6 h-6 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
              </svg>
              注册账号
            </Link>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 border-t border-gray-200 dark:border-dark-600">
        <p className="text-center text-gray-600 dark:text-gray-400 text-sm">
          © {new Date().getFullYear()} Intelli-Job. 基于 AI 技术的智能求职平台
        </p>
      </div>
    </main>
  )
}
