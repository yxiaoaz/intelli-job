/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  // 暗色一轨：仅由 <html class="dark"> 控制，globals.css 不再保留 prefers-color-scheme 分支
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // 品牌蓝 #4176E6（决策 2）——同名重写：现存 primary-* 引用自动换血
        // 保留旧 50/100/200/300/400/500/600/700/800/900 全档键名（决策 9“同名重写优先
        // 于删改”的铁律要求），300/700/900 为插值补齐，避免残留引用（大量
        // dark:hover:bg-primary-900/xx、border-primary-700/xx 等）编译失效
        primary: {
          50: '#EDF3FE',  // 用户气泡底
          100: '#D3E2FF', // 选中
          200: '#A8C4F4', // disabled / focus ring
          300: '#8BB1F9',
          400: '#679EFE',
          500: '#4176E6', // 主行动色
          600: '#3460C8', // hover
          700: '#294DA6',
          800: '#1E3A85',
          900: '#152758',
        },
        // 语义色（决策 2）：success / warning / danger
        success: {
          50: '#F1F8E9',
          100: '#D7ECC0',
          400: '#74A83D',
          600: '#3B6D11',
          800: '#1F3D08',
        },
        warning: {
          50: '#FDF3E4',
          100: '#F9E3C0',
          400: '#DDA144',
          600: '#BA7517',
          800: '#6B4008',
        },
        danger: {
          50: '#FBEBEB',
          100: '#F3C9C9',
          400: '#D16B6B',
          600: '#A32D2D',
          800: '#5C1717',
        },
        // accent / dark 两个旧色板键已在 Phase 4.7 退役删除：全站无 accent-* 与 dark-N 引用，
        // 主题表面统一走 bg-base / bg-layer1 / bg-layer2 与 text-900/700/500/400 语义类
        // （注意：darkMode: 'class' 与 html.dark 选择器不受此删除影响）
      },
      // 桥接 globals.css 的语义变量，组件可直接用 bg-base/bg-layer1/border-l1/text-500 等，
      // 无需再写 dark: 分支（决策 1：组件禁止写主题分支）
      backgroundColor: {
        base: 'var(--ij-bg-base)',
        layer1: 'var(--ij-bg-layer1)',
        layer2: 'var(--ij-bg-layer2)',
        'hover-neutral': 'var(--ij-hover-neutral)',
        'hover-primary': 'var(--ij-hover-primary)',
        // 彩色浅底（chip/提示块/用户气泡）——深浅两套由 alias 层覆盖
        'tint-primary': 'var(--ij-tint-primary)',
        'tint-success': 'var(--ij-tint-success)',
        'tint-warning': 'var(--ij-tint-warning)',
        'tint-danger': 'var(--ij-tint-danger)',
        'user-bubble': 'var(--ij-user-bubble)',
      },
      borderColor: {
        l1: 'var(--ij-border-l1)',
        l2: 'var(--ij-border-l2)',
        l3: 'var(--ij-border-l3)',
        l4: 'var(--ij-border-l4)',
        'tint-primary': 'var(--ij-tint-primary-border)',
        'tint-success': 'var(--ij-tint-success-border)',
        'tint-warning': 'var(--ij-tint-warning-border)',
        'tint-danger': 'var(--ij-tint-danger-border)',
      },
      // 列表分隔线（divide-*）同 borders 语义，否则不会拿到 borderColor 扩展键
      divideColor: {
        l1: 'var(--ij-border-l1)',
        l2: 'var(--ij-border-l2)',
        l3: 'var(--ij-border-l3)',
        l4: 'var(--ij-border-l4)',
      },
      textColor: {
        900: 'var(--ij-text-900)',
        700: 'var(--ij-text-700)',
        500: 'var(--ij-text-500)',
        400: 'var(--ij-text-400)',
        'tint-primary': 'var(--ij-tint-primary-text)',
        'tint-success': 'var(--ij-tint-success-text)',
        'tint-warning': 'var(--ij-tint-warning-text)',
        'tint-danger': 'var(--ij-tint-danger-text)',
        'user-bubble': 'var(--ij-user-bubble-text)',
      },
      // 决策 3：中文优先的系统字体栈，删除 Inter/Poppins（font-display 键一并退役，
      // 残余 `font-display` 类名在 Phase 4 清理文件中统一移除，不影响渲染）
      fontFamily: {
        sans: [
          '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'PingFang SC',
          'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', 'Arial', 'sans-serif',
        ],
        mono: ['"SF Mono"', '"JetBrains Mono"', 'Consolas', 'Menlo', 'PingFang SC', 'monospace'],
      },
      // 决策 3：字号与行高成对，禁止裸 text-N（仅覆盖常用档，3xl 及以上保留默认）
      fontSize: {
        xs: ['12px', '18px'],
        sm: ['13px', '20px'],
        base: ['14px', '22px'],
        md: ['15px', '24px'],
        lg: ['16px', '28px'],
        xl: ['20px', '28px'],
        '2xl': ['24px', '32px'],
      },
      // 决策 3：全站两档字重（normal/medium 为新增档，bold 保留供 markdown 渲染等场景使用）
      fontWeight: {
        normal: '400',
        medium: '500',
      },
      // 决策 4：圆角语义化
      borderRadius: {
        input: '8px',
        menu: '12px',
        btn: '18px',
        dialog: '24px',
      },
      // 决策 4：阴影三档中性，删除全部 glow（glow/glow-lg/cyan-glow 不再定义，
      // 残余 shadow-glow 引用会静默失效，Phase 4 统一清理类名）
      boxShadow: {
        lv1: '0 2px 4px rgba(0,0,0,0.05)',
        lv2: '0 4px 12px rgba(0,0,0,0.02), 0 2px 8px rgba(0,0,0,0.04)',
        lv3: '0 0 1px rgba(0,0,0,0.20), 0 0 4px rgba(0,0,0,0.02), 0 12px 32px rgba(0,0,0,0.08)',
      },
      // 决策 5：动效收敛——统一缓动 + 三档时长
      transitionTimingFunction: {
        ds: 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
      transitionDuration: {
        fast: '100ms',
        base: '200ms',
        slow: '300ms',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        'slide-up': 'slideUp 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'tool-shimmer': 'tool-shimmer 1.6s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
