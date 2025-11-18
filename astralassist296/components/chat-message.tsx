import { Card } from '@/components/ui/card';
import { Sparkles } from 'lucide-react';

interface ChatMessageProps {
  message: {
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
  };
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isAssistant = message.role === 'assistant';

  return (
    <div className={`flex gap-3 ${isAssistant ? 'justify-start' : 'justify-end'}`}>
      {isAssistant && (
        <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-1">
          <Sparkles className="w-4 h-4 text-primary" />
        </div>
      )}

      <div className={`max-w-2xl ${isAssistant ? '' : 'flex justify-end'}`}>
        <Card
          className={`rounded-2xl px-4 py-3 border ${
            isAssistant
              ? 'bg-card/40 border-border/50 text-foreground'
              : 'bg-primary text-primary-foreground border-primary/50'
          }`}
        >
          <p className="text-sm leading-relaxed">{message.content}</p>
        </Card>
        <p className={`text-xs mt-2 ${isAssistant ? 'text-left' : 'text-right'} text-muted-foreground`}>
          {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>

      {!isAssistant && (
        <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center flex-shrink-0 mt-1">
          <span className="text-xs font-semibold text-secondary-foreground">U</span>
        </div>
      )}
    </div>
  );
}
