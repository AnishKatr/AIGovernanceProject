export interface AgentDecision {
  recommended_agent: string;
  reasoning: string;
}

export interface RetrievedContext {
  id?: string;
  score?: number;
  text: string;
  metadata?: Record<string, any>;
}

export interface QueryResponse {
  decision: AgentDecision;
  result: {
    response: string;
    contexts: RetrievedContext[];
    agents_used: string[];
    agent_strategy: string;
  };
}

const DEFAULT_BACKEND_URL = 'http://localhost:5001';

export async function queryOrchestrator(prompt: string): Promise<QueryResponse> {
  const baseUrl = process.env.NEXT_PUBLIC_BACKEND_URL || DEFAULT_BACKEND_URL;
  const url = `${baseUrl.replace(/\/$/, '')}/api/query`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query: prompt }),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Backend error (${response.status})`);
  }

  return response.json();
}
