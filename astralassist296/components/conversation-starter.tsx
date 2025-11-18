import { Card } from '@/components/ui/card';
import { ArrowRight, Mail, FileText, BarChart3 } from 'lucide-react';

interface ConversationStarterProps {
  onSelect: (action: string) => void;
}

export default function ConversationStarter({ onSelect }: ConversationStarterProps) {
  const starters = [
    {
      icon: Mail,
      title: 'Organize Emails',
      description: 'Help me organize and categorize my inbox',
    },
    {
      icon: FileText,
      title: 'Draft Report',
      description: 'Generate and format an expense report',
    },
    {
      icon: BarChart3,
      title: 'Analyze Data',
      description: 'Summarize and extract insights from documents',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {starters.map((starter, idx) => {
        const Icon = starter.icon;
        return (
          <Card
            key={idx}
            className="p-4 border border-border/50 hover:border-primary/50 hover:bg-card/60 cursor-pointer transition-all group"
            onClick={() => onSelect(starter.description)}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Icon className="w-5 h-5 text-primary" />
                  <h3 className="font-semibold text-sm text-foreground">{starter.title}</h3>
                </div>
                <p className="text-xs text-muted-foreground">{starter.description}</p>
              </div>
              <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
            </div>
          </Card>
        );
      })}
    </div>
  );
}
