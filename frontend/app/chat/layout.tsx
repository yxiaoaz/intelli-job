'use client';

import { ChatProvider } from '@/components/ChatContext';

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <ChatProvider>{children}</ChatProvider>;
}
