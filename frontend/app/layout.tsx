import type { Metadata } from 'next'
import './globals.css'
import Script from 'next/script'
import { Providers } from '@/components/Providers'
import { Toaster } from 'sonner'

// 决策 3：删除 next/font/google 的 Inter 加载——它与 globals.css 的字体栈是两条独立路径，
// inter.className 会覆盖 body 规则，重新引入「Inter 无中文字形导致回落」的问题。
// 全站改用系统中文栈（见 tailwind.config.js fontFamily.sans / globals.css body）。

export const metadata: Metadata = {
  title: 'Intelli-Job | AI求职助手',
  description: '基于AI的智能求职与职位匹配平台',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        <Script id="theme-init" strategy="beforeInteractive">
          {`
            if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
              document.documentElement.classList.add('dark');
            }
          `}
        </Script>
      </head>
      <body suppressHydrationWarning>
        <Providers>{children}</Providers>
        <Toaster position="bottom-right" richColors closeButton />
      </body>
    </html>
  )
}
