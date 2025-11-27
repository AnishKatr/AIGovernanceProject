'use client';

import { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import ChatMessage from '@/components/chat-message';
import AgentStatus from '@/components/agent-status';
import Sidebar from '@/components/sidebar';
import ConversationStarter from '@/components/conversation-starter';
import { Send, Sparkles, Menu, X } from 'lucide-react';
import type { AgentDecision, RetrievedContext, HrEmailRequest, HistoryMessage } from '@/lib/api';
import { queryOrchestrator, sendHrEmail, syncDrive } from '@/lib/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  agents?: string[];
  contexts?: RetrievedContext[];
  decision?: AgentDecision;
  error?: boolean;
}

interface Conversation {
  id: string;
  title: string;
  timestamp: Date;
  messageCount: number;
}

export default function Home() {
  const sessionId = useRef<string>(
    typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `session-${Date.now()}`
  );
  const [messages, setMessages] = useState<Message[]>([]);
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
  const [hrForm, setHrForm] = useState({
    employeeId: '',
    employeeName: '',
    subject: 'Account Update',
    body:
      'Hi {first_name},\n\nWe are refreshing HR records. Your role is {designation} in {department}. Please reply if anything looks incorrect.\n\nThanks,\nHR Ops',
    driveFileId: '',
    sendNow: false,
  });
  const [hrStatus, setHrStatus] = useState<string | null>(null);
  const [driveStatus, setDriveStatus] = useState<string | null>(null);
  const [hrBusy, setHrBusy] = useState(false);
  const [driveBusy, setDriveBusy] = useState(false);
  const hasLoadedHistory = useRef(false);

  // Load chat history from localStorage once
  useEffect(() => {
    if (hasLoadedHistory.current) return;
    hasLoadedHistory.current = true;
    if (typeof window === 'undefined') return;
    const raw = localStorage.getItem('astral-chat-history');
    if (raw) {
      try {
        const parsed = JSON.parse(raw) as Message[];
        const normalized = parsed.map((m) => ({
          ...m,
          timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
        }));
        if (normalized.length > 0) {
          setMessages(normalized);
          return;
        }
      } catch (err) {
        console.error('Failed to parse chat history', err);
      }
    } else {
      setMessages([
        {
          id: '1',
          role: 'assistant',
          content:
            "Welcome to Astral Assist! I'm your AI-powered multi-agent orchestrator. I can help you with emails, drive management, expense reports, and much more. What would you like to accomplish today?",
          timestamp: new Date(),
        },
      ]);
      return;
    }
    // Fallback welcome if history was empty or parsing failed.
    setMessages([
      {
        id: '1',
        role: 'assistant',
        content:
          "Welcome to Astral Assist! I'm your AI-powered multi-agent orchestrator. I can help you with emails, drive management, expense reports, and much more. What would you like to accomplish today?",
        timestamp: new Date(),
      },
    ]);
  }, []);

  // Persist chat history
  useEffect(() => {
    if (typeof window === 'undefined' || messages.length === 0) return;
    const serializable = messages.map((m) => ({
      ...m,
      timestamp: m.timestamp.toISOString(),
    }));
    localStorage.setItem('astral-chat-history', JSON.stringify(serializable));
  }, [messages]);

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

  const mapAgentName = (agentId: string) => {
    const normalized = agentId.toLowerCase();
    const mapping: Record<string, string> = {
      rag: 'Knowledge Base RAG',
      email: 'Email Agent',
      drive: 'Drive Agent',
      hr: 'HR Agent',
    };
    return mapping[normalized] || agentId;
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim()) return;

    const historyPayload: HistoryMessage[] = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      const data = await queryOrchestrator(userMessage.content, historyPayload, sessionId.current);
      const ragAgents = data.result.agents_used.map(mapAgentName);
      const agentBadges = Array.from(new Set(['Task Decomposition', 'Agent Routing', ...ragAgents]));

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.result.response,
        timestamp: new Date(),
        agents: agentBadges,
        contexts: undefined, // hide contexts in UI to avoid clutter/PII
        decision: data.decision,
        error: !!data.result.error,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content:
          error instanceof Error
            ? `I hit an error while contacting the orchestrator: ${error.message}`
            : 'I hit an unexpected error while contacting the orchestrator.',
        timestamp: new Date(),
        error: true,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } finally {
      setIsLoading(false);
    }

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

  const handleHrSend = async () => {
    if (!hrForm.subject.trim()) {
      setHrStatus('Subject is required.');
      return;
    }
    if (!hrForm.employeeId.trim() && !hrForm.employeeName.trim()) {
      setHrStatus('Provide an employee ID or name.');
      return;
    }

    setHrBusy(true);
    setHrStatus(null);
    try {
      const payload: HrEmailRequest = {
        subject: hrForm.subject,
        body: hrForm.body,
        drive_file_id: hrForm.driveFileId || undefined,
        send: hrForm.sendNow,
      };
      if (hrForm.employeeId.trim()) {
        payload.employee_id = Number(hrForm.employeeId);
      } else {
        payload.name = hrForm.employeeName;
      }

      const res = await sendHrEmail(payload);
      if (res.error) throw new Error(res.error);

      const statusLabel =
        res.send_result?.status === 'sent'
          ? `Sent to ${res.employee?.email} (message id: ${res.send_result?.message_id || 'n/a'})`
          : 'Prepared draft (dry run).';
      setHrStatus(statusLabel);
    } catch (error) {
      setHrStatus(error instanceof Error ? error.message : 'Failed to trigger HR email flow.');
    } finally {
      setHrBusy(false);
    }
  };

  const handleDriveSync = async () => {
    setDriveBusy(true);
    setDriveStatus(null);
    try {
      const res = await syncDrive();
      if (res.error) throw new Error(res.error);
      setDriveStatus('Employee database refreshed in Drive.');
    } catch (error) {
      setDriveStatus(error instanceof Error ? error.message : 'Drive sync failed.');
    } finally {
      setDriveBusy(false);
    }
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
      <div className="flex-1 flex flex-col overflow-hidden min-h-0">
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

        {/* Main scrollable column: chat first, then ops */}
        <div className="flex-1 overflow-auto">
          <div className="max-w-6xl mx-auto px-4 py-4 space-y-4">
            {/* Conversation */}
            <div className="w-full bg-card/10 border border-border/40 rounded-2xl shadow-sm flex flex-col min-h-[320px]">
              <div className="border-b border-border/40 px-4 py-3 flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-foreground">Conversation</p>
                  <p className="text-xs text-muted-foreground">Multi-agent responses with context.</p>
                </div>
              </div>
              <div className="flex-1 min-h-0 overflow-hidden">
                {messages.length <= 1 && !isLoading ? (
                  <div className="h-full flex flex-col items-center justify-center px-6 py-8">
                    <div className="max-w-2xl w-full space-y-8">
                      <div className="text-center space-y-3">
                        <div className="w-16 h-16 rounded-full bg-gradient-to-br from-primary/30 to-accent/30 flex items-center justify-center mx-auto">
                          <Sparkles className="w-8 h-8 text-primary" />
                        </div>
                        <h2 className="text-2xl font-bold text-foreground">What can I help with?</h2>
                        <p className="text-sm text-muted-foreground">
                          Ask in natural language — I can draft emails, sync Drive, or answer with RAG context.
                        </p>
                      </div>
                      <ConversationStarter onSelect={handleQuickAction} />
                    </div>
                  </div>
                ) : (
                  <ScrollArea className="h-full px-4 py-4">
                    <div className="max-w-2xl mx-auto space-y-6 pb-4 min-h-[200px]" ref={scrollRef}>
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
              <div className="border-t border-border/30 bg-background/70 backdrop-blur-md rounded-b-2xl">
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

            {/* Ops shortcuts below chat */}
            <div className="w-full border border-border/40 bg-muted/10 rounded-2xl shadow-sm">
              <div className="px-4 py-4">
                <div className="max-w-6xl mx-auto grid gap-4 md:grid-cols-2">
                  <Card className="border-border/60 shadow-none">
                    <CardHeader>
                      <CardTitle>HR Email Agent</CardTitle>
                      <CardDescription>Pull employee data and compose an email with optional Drive attachment.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <Label htmlFor="employeeId" className="text-xs text-muted-foreground">
                            Employee ID
                          </Label>
                          <Input
                            id="employeeId"
                            placeholder="e.g., 3"
                            value={hrForm.employeeId}
                            onChange={(e) => setHrForm({ ...hrForm, employeeId: e.target.value })}
                            disabled={hrBusy}
                            className="mt-1"
                          />
                        </div>
                        <div>
                          <Label htmlFor="employeeName" className="text-xs text-muted-foreground">
                            or Name
                          </Label>
                          <Input
                            id="employeeName"
                            placeholder="e.g., Jane Doe"
                            value={hrForm.employeeName}
                            onChange={(e) => setHrForm({ ...hrForm, employeeName: e.target.value, employeeId: '' })}
                            disabled={hrBusy}
                            className="mt-1"
                          />
                        </div>
                      </div>
                      <div>
                        <Label htmlFor="subject" className="text-xs text-muted-foreground">
                          Subject
                        </Label>
                        <Input
                          id="subject"
                          placeholder="Subject"
                          value={hrForm.subject}
                          onChange={(e) => setHrForm({ ...hrForm, subject: e.target.value })}
                          disabled={hrBusy}
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <Label htmlFor="body" className="text-xs text-muted-foreground">
                          Body (supports {'{'}{'}'}first_name{'{'}{'}'}, {'{'}{'}'}department{'{'}{'}'}, etc.)
                        </Label>
                        <Textarea
                          id="body"
                          value={hrForm.body}
                          onChange={(e) => setHrForm({ ...hrForm, body: e.target.value })}
                          disabled={hrBusy}
                          className="mt-1 text-sm min-h-[120px]"
                        />
                      </div>
                      <div>
                        <Label htmlFor="driveFile" className="text-xs text-muted-foreground">
                          Drive File ID (optional attachment)
                        </Label>
                        <Input
                          id="driveFile"
                          placeholder="1Abc...xyz"
                          value={hrForm.driveFileId}
                          onChange={(e) => setHrForm({ ...hrForm, driveFileId: e.target.value })}
                          disabled={hrBusy}
                          className="mt-1"
                        />
                      </div>
                      <div className="flex items-center justify-between rounded-lg border border-border/50 px-3 py-2">
                        <div className="space-y-0.5">
                          <p className="text-sm font-medium">Send via Gmail</p>
                          <p className="text-xs text-muted-foreground">Off = dry-run draft only</p>
                        </div>
                        <Switch
                          checked={hrForm.sendNow}
                          onCheckedChange={(checked) => setHrForm({ ...hrForm, sendNow: checked })}
                          disabled={hrBusy}
                        />
                      </div>
                      <div className="flex items-center gap-3">
                        <Button onClick={handleHrSend} disabled={hrBusy} className="gap-2">
                          <Send className="w-4 h-4" />
                          {hrBusy ? 'Working...' : hrForm.sendNow ? 'Send Email' : 'Prepare Draft'}
                        </Button>
                        {hrStatus && <p className="text-xs text-muted-foreground">{hrStatus}</p>}
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="border-border/60 shadow-none">
                    <CardHeader>
                      <CardTitle>Drive Sync</CardTitle>
                      <CardDescription>Refresh employee_database.csv in your shared Drive folder.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <p className="text-sm text-muted-foreground">
                        Uses the HR API as source of truth and updates the shared Dummy Folder.
                      </p>
                      <Button onClick={handleDriveSync} disabled={driveBusy} className="w-full">
                        {driveBusy ? 'Syncing...' : 'Sync Employee Database'}
                      </Button>
                      {driveStatus && <p className="text-xs text-muted-foreground">{driveStatus}</p>}
                    </CardContent>
                  </Card>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
