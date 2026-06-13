// ✅ 移除 ChatProvider，改为在 /chat layout 中单独使用
// Providers 现在只负责全局的 Provider（如 Toaster），不再包含 ChatProvider

export function Providers({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
