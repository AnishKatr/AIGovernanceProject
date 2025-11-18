'use client';

import { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import ChatMessage from '@/components/chat-message';
import AgentStatus from '@/components/agent-status';
import Sidebar from '@/components/sidebar';
import ConversationStarter from '@/components/conversation-starter';
import { Send, Sparkles, Menu, X } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  agents?: string[];
}

interface Conversation {
  id: string;
  title: string;
  timestamp: Date;
  messageCount: number;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Welcome to Astral Assist! I\'m your AI-powered multi-agent orchestrator. I can help you with emails, drive management, expense reports, and much more. What would you like to accomplish today?',
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [conversations, setConversations] = useState<Conversation[]>([
    {
      id: '1',
      title: 'Email Workflow Setup',
      timestamp: new Date(Date.now() - 3600000),
      messageCount: 12,
    },
    {
      id: '2',
      title: 'Expense Report Automation',
      timestamp: new Date(Date.now() - 86400000),
      messageCount: 8,
    },
  ]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    setTimeout(() => {
      if (scrollRef.current) {
        scrollRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
      }
    }, 0);
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    setTimeout(() => {
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'I\'ve processed your request. The orchestrator has analyzed your task and is routing it to the appropriate agents based on your needs. Results will be compiled and presented shortly.',
        timestamp: new Date(),
        agents: ['Task Decomposition', 'Agent Routing'],
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsLoading(false);
    }, 1500);

    inputRef.current?.focus();
  };

  const handleQuickAction = (action: string) => {
    setInputValue(action);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const handleNewConversation = () => {
    setMessages([
      {
        id: '1',
        role: 'assistant',
        content: 'Welcome back! What can I help you with today?',
        timestamp: new Date(),
      },
    ]);
    setInputValue('');
  };

  return (
    <div className="h-screen bg-background flex overflow-hidden">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        conversations={conversations}
        onNewConversation={handleNewConversation}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="border-b border-border/40 bg-background/80 backdrop-blur-md sticky top-0 z-40">
          <div className="px-4 py-3 flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="lg:hidden p-2 hover:bg-card rounded-lg transition-colors"
              >
                {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-accent flex items-center justify-center">
                  <Sparkles className="w-6 h-6 text-primary-foreground" />
                </div>
                <div>
                  <h1 className="text-lg font-bold text-foreground">Astral Assist</h1>
                  <p className="text-xs text-muted-foreground">AI Orchestrator</p>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs text-muted-foreground">Active</span>
            </div>
          </div>
        </div>

        {/* Chat Content Area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-hidden">
            {messages.length === 1 && !isLoading ? (
              <div className="h-full flex flex-col items-center justify-center px-4 py-8">
                <div className="max-w-2xl w-full space-y-8">
                  <div className="text-center space-y-3">
                    <div className="w-16 h-16 rounded-full bg-gradient-to-br from-primary/30 to-accent/30 flex items-center justify-center mx-auto">
                      <Sparkles className="w-8 h-8 text-primary" />
                    </div>
                    <h2 className="text-2xl font-bold text-foreground">What can I help with?</h2>
                    <p className="text-sm text-muted-foreground">
                      I can assist with email management, drive organization, expense reports, and more.
                    </p>
                  </div>
                  <ConversationStarter onSelect={handleQuickAction} />
                </div>
              </div>
            ) : (
              <ScrollArea className="h-full px-4 py-8">
                <div className="max-w-2xl mx-auto space-y-6 pb-4" ref={scrollRef}>
                  {messages.map((message) => (
                    <div key={message.id}>
                      <ChatMessage message={message} />
                      {message.agents && message.agents.length > 0 && (
                        <div className="mt-3 ml-0 flex flex-wrap gap-2">
                          {message.agents.map((agent) => (
                            <AgentStatus key={agent} agent={agent} />
                          ))}
                        </div>
                      )}
                    </div>
                  ))}

                  {isLoading && (
                    <div className="flex gap-3 animate-fade-in">
                      <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-1">
                        <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                      </div>
                      <div className="flex-1">
                        <div className="rounded-2xl bg-card/40 border border-border/50 p-4">
                          <div className="flex gap-2">
                            <div className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0ms' }} />
                            <div className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: '150ms' }} />
                            <div className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: '300ms' }} />
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </ScrollArea>
            )}
          </div>

          {/* Input Area */}
          <div className="border-t border-border/40 bg-background/80 backdrop-blur-md">
            <div className="px-4 py-4">
              <form onSubmit={handleSendMessage} className="max-w-2xl mx-auto space-y-3">
                <div className="flex gap-3">
                  <Input
                    ref={inputRef}
                    type="text"
                    placeholder="Ask anything... emails, drive, reports"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    disabled={isLoading}
                    className="bg-input border-border/50 text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:ring-primary/30 text-sm"
                  />
                  <Button
                    type="submit"
                    disabled={isLoading || !inputValue.trim()}
                    className="bg-primary hover:bg-primary/90 text-primary-foreground gap-2 px-6"
                  >
                    <Send className="w-4 h-4" />
                    <span className="hidden sm:inline">Send</span>
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground pl-1">
                  Powered by Groq LLM + Pinecone RAG. Responses encrypted end-to-end.
                </p>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
