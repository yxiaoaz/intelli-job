'use client';

import { ChatProvider } from './ChatContext';

export function Providers({ children }: { children: React.ReactNode }) {
  return <ChatProvider>{children}</ChatProvider>;
}
