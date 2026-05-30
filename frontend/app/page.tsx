'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Briefcase, MessageSquare, User } from 'lucide-react'

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-between p-24">
      <div className="z-10 max-w-5xl w-full items-center justify-between font-mono text-sm lg:flex">
        <h1 className="text-4xl font-bold mb-8">Intelli-Job</h1>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 w-full mt-12">
          <Link href="/dashboard" className="p-6 border rounded-lg hover:bg-gray-100 transition-all group">
            <Briefcase className="w-10 h-10 mb-4 text-blue-600" />
            <h2 className="text-xl font-semibold">职位匹配</h2>
            <p className="mt-2 text-gray-600">上传简历，智能推荐最适合你的岗位</p>
          </Link>
          
          <Link href="/chat" className="p-6 border rounded-lg hover:bg-gray-100 transition-all group">
            <MessageSquare className="w-10 h-10 mb-4 text-green-600" />
            <h2 className="text-xl font-semibold">求职助手</h2>
            <p className="mt-2 text-gray-600">与AI对话，获取个性化求职建议</p>
          </Link>
          
          <Link href="/profile" className="p-6 border rounded-lg hover:bg-gray-100 transition-all group">
            <User className="w-10 h-10 mb-4 text-purple-600" />
            <h2 className="text-xl font-semibold">我的画像</h2>
            <p className="mt-2 text-gray-600">管理你的技能树和求职偏好</p>
          </Link>
        </div>
      </div>
    </main>
  )
}
