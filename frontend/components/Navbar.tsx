'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Menu, X, LogOut } from 'lucide-react';
import { buttonClasses } from './ui/Button';

interface NavbarProps {
  currentPath: string;
}

const navItems = [
  { label: '职位搜索', href: '/dashboard' },
  { label: '我的简历', href: '/resumes' },
  { label: '求职看板', href: '/bookmarks' },
  { label: 'AI助手', href: '/chat' },
  { label: '我的资料', href: '/profile' },
];

/**
 * ui-redesign 决策 5.4：导航激活态 = 文字加深 + 底部 2px 指示条（不再是主蓝整块高亮）。
 * glass 类名在此保留（Phase 1 已重写为中性表面），是全站最后一处 glass 引用。
 */
export default function Navbar({ currentPath }: NavbarProps) {
  const router = useRouter();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    router.push('/login');
  };

  const handleNavClick = (href: string) => {
    setIsMobileMenuOpen(false);
    router.push(href);
  };

  return (
    <header className="glass shadow-lv1 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
        {/* Logo —— 渐变文字仅此处允许使用（决策 1.5） */}
        <button
          onClick={() => router.push('/dashboard')}
          className="text-lg font-medium gradient-text hover:opacity-80 transition-opacity duration-base ease-ds"
        >
          Intelli-Job
        </button>

        {/* Desktop Navigation */}
        <nav className="hidden md:flex items-center space-x-6">
          {navItems.map((item) => {
            const isActive = currentPath === item.href;
            return (
              <button
                key={item.href}
                onClick={() => handleNavClick(item.href)}
                aria-current={isActive ? 'page' : undefined}
                className={`relative py-1 text-sm border-b-2 transition-colors duration-base ease-ds ${
                  isActive
                    ? 'text-900 font-medium border-primary-500'
                    : 'text-500 font-normal border-transparent hover:text-900'
                }`}
              >
                {item.label}
              </button>
            );
          })}
          <button onClick={handleLogout} className={buttonClasses('ghost', 'sm', 'text-tint-danger hover:text-danger-800')}>
            <LogOut className="w-4 h-4" />
            退出
          </button>
        </nav>

        {/* Mobile Menu Toggle */}
        <button
          onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          className="md:hidden p-2 rounded-input text-700 hover:bg-hover-neutral transition-colors duration-base ease-ds"
          aria-label={isMobileMenuOpen ? '关闭菜单' : '打开菜单'}
        >
          {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Mobile Menu Dropdown */}
      {isMobileMenuOpen && (
        <div className="md:hidden border-t border-l1 bg-base animate-fade-in">
          <nav className="px-4 py-3 space-y-1">
            {navItems.map((item) => (
              <button
                key={item.href}
                onClick={() => handleNavClick(item.href)}
                aria-current={currentPath === item.href ? 'page' : undefined}
                className={`block w-full text-left px-4 py-3 rounded-menu text-sm border-l-2 transition-colors duration-base ease-ds ${
                  currentPath === item.href
                    ? 'bg-tint-primary text-900 font-medium border-primary-500'
                    : 'text-700 border-transparent hover:bg-hover-neutral'
                }`}
              >
                {item.label}
              </button>
            ))}
            <button
              onClick={handleLogout}
              className="block w-full text-left px-4 py-3 rounded-menu text-sm text-tint-danger hover:bg-hover-neutral transition-colors duration-base ease-ds"
            >
              退出登录
            </button>
          </nav>
        </div>
      )}
    </header>
  );
}
