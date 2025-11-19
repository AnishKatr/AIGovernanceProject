import { Card } from '@/components/ui/card';
import { Sparkles } from 'lucide-react';
import type { AgentDecision, RetrievedContext } from '@/lib/api';

interface ChatMessageProps {
  message: {
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    contexts?: RetrievedContext[];
    decision?: AgentDecision;
    error?: boolean;
  };
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isAssistant = message.role === 'assistant';

  return (
    <div className={`flex items-start gap-3 ${isAssistant ? 'justify-start' : 'justify-end'}`}>
      {isAssistant && (
        <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
          <Sparkles className="w-4 h-4 text-primary" />
        </div>
      )}

      <div className={`max-w-2xl flex flex-col gap-2 ${isAssistant ? 'items-start' : 'items-end'}`}>
        <Card
          className={`rounded-2xl px-4 py-3 border space-y-3 ${
            isAssistant
              ? message.error
                ? 'bg-destructive/10 border-destructive/50 text-destructive'
                : 'bg-card/40 border-border/50 text-foreground'
              : 'bg-primary text-primary-foreground border-primary/50'
          }`}
        >
          <p className="text-sm leading-relaxed">{message.content}</p>

          {isAssistant && message.decision && (
            <p className="text-[11px] text-muted-foreground">
              Routed to <span className="font-medium text-foreground">{message.decision.recommended_agent}</span> —{' '}
              {message.decision.reasoning}
            </p>
          )}

          {isAssistant && message.contexts && message.contexts.length > 0 && (
            <div className="space-y-2">
              {message.contexts.map((context, index) => (
                <div
                  key={`${context.id || index}`}
                  className="rounded-xl border border-border/50 bg-background/60 p-3"
                >
                  <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
                    {context.metadata?.source || context.metadata?.file_name || `Document ${index + 1}`}
                    {context.score ? ` · score ${context.score.toFixed(2)}` : ''}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">{context.text}</p>
                </div>
              ))}
            </div>
          )}
        </Card>
        <p className="text-xs text-muted-foreground">
          {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>

      {!isAssistant && (
        <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center flex-shrink-0">
          <span className="text-xs font-semibold text-secondary-foreground">U</span>
        </div>
      )}
    </div>
  );
}
