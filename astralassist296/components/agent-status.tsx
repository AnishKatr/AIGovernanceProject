import { Badge } from '@/components/ui/badge';
import { CheckCircle2, Zap } from 'lucide-react';

interface AgentStatusProps {
  agent: string;
}

export default function AgentStatus({ agent }: AgentStatusProps) {
  const agents = {
    'Task Decomposition': { icon: Zap, color: 'bg-purple-500/20 text-purple-400 border-purple-500/30' },
    'Agent Routing': { icon: Zap, color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
    'Email Agent': { icon: CheckCircle2, color: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30' },
    'Drive Agent': { icon: CheckCircle2, color: 'bg-green-500/20 text-green-400 border-green-500/30' },
    'Expense Report': { icon: CheckCircle2, color: 'bg-orange-500/20 text-orange-400 border-orange-500/30' },
  };

  const agentConfig = agents[agent as keyof typeof agents] || {
    icon: CheckCircle2,
    color: 'bg-primary/20 text-primary border-primary/30',
  };

  const Icon = agentConfig.icon;

  return (
    <Badge variant="outline" className={`${agentConfig.color} gap-1.5 px-3 py-1.5 font-medium border`}>
      <Icon className="w-3 h-3" />
      {agent}
    </Badge>
  );
}
