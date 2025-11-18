'use client';

import { Button } from '@/components/ui/button';
import { Plus, History, Settings, LogOut, Zap } from 'lucide-react';
import { useState } from 'react';

interface Conversation {
  id: string;
  title: string;
  timestamp: Date;
  messageCount: number;
}

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  conversations: Conversation[];
  onNewConversation: () => void;
}

export default function Sidebar({ open, onClose, conversations, onNewConversation }: SidebarProps) {
  const [activeConversation, setActiveConversation] = useState<string | null>(null);

  const formatTime = (date: Date) => {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <>
      {/* Mobile Overlay */}
      {open && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <div
        className={`fixed lg:static w-64 h-screen bg-sidebar border-r border-sidebar-border flex flex-col transition-all duration-300 z-40 ${
          open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        {/* New Conversation Button */}
        <div className="p-4 border-b border-sidebar-border">
          <Button
            onClick={() => {
              onNewConversation();
              onClose();
              setActiveConversation(null);
            }}
            className="w-full bg-sidebar-primary hover:bg-sidebar-primary/90 text-sidebar-primary-foreground gap-2 justify-center"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </Button>
        </div>

        {/* Conversation History */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-2">
          <p className="px-2 text-xs font-semibold text-sidebar-accent-foreground uppercase tracking-wide mb-3">
            Recent Conversations
          </p>
          {conversations.map((conv) => (
            <button
              key={conv.id}
              onClick={() => {
                setActiveConversation(conv.id);
                onClose();
              }}
              className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors text-sm truncate ${
                activeConversation === conv.id
                  ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                  : 'text-sidebar-foreground hover:bg-sidebar-accent/30'
              }`}
            >
              <div className="truncate font-medium">{conv.title}</div>
              <div className="text-xs text-sidebar-accent-foreground opacity-70">
                {formatTime(conv.timestamp)} • {conv.messageCount} messages
              </div>
            </button>
          ))}
        </div>

        {/* Footer Actions */}
        <div className="border-t border-sidebar-border p-3 space-y-2">
          <Button
            variant="ghost"
            className="w-full justify-start gap-2 text-sidebar-foreground hover:bg-sidebar-accent/20"
          >
            <Zap className="w-4 h-4" />
            <span className="text-sm">Features</span>
          </Button>
          <Button
            variant="ghost"
            className="w-full justify-start gap-2 text-sidebar-foreground hover:bg-sidebar-accent/20"
          >
            <Settings className="w-4 h-4" />
            <span className="text-sm">Settings</span>
          </Button>
          <Button
            variant="ghost"
            className="w-full justify-start gap-2 text-sidebar-foreground hover:bg-sidebar-accent/20"
          >
            <LogOut className="w-4 h-4" />
            <span className="text-sm">Sign Out</span>
          </Button>
        </div>
      </div>
    </>
  );
}
