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
    error?: string;
  };
}

const DEFAULT_BACKEND_URL = 'http://localhost:5001';

export interface HistoryMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface HrEmailRequest {
  employee_id?: number;
  name?: string;
  subject: string;
  body?: string;
  drive_file_id?: string;
  attachments?: string[];
  send?: boolean;
  hr_url?: string;
}

export interface HrEmailResponse {
  status?: string;
  error?: string;
  employee?: Record<string, any>;
  send_result?: {
    status: string;
    message_id?: string;
    log_id?: string;
  };
}

export interface DriveSyncResponse {
  status?: string;
  error?: string;
  folder_id?: string;
  csv_name?: string;
}

function backendBaseUrl() {
  return (process.env.NEXT_PUBLIC_BACKEND_URL || DEFAULT_BACKEND_URL).replace(/\/$/, '');
}

export async function queryOrchestrator(prompt: string, history?: HistoryMessage[], sessionId?: string): Promise<QueryResponse> {
  const url = `${backendBaseUrl()}/api/query`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query: prompt, history: history || [], session_id: sessionId }),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Backend error (${response.status})`);
  }

  return response.json();
}

export async function sendHrEmail(payload: HrEmailRequest): Promise<HrEmailResponse> {
  const response = await fetch(`${backendBaseUrl()}/api/hr/email`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Backend error (${response.status})`);
  }
  return response.json();
}

export async function syncDrive(payload?: { hr_url?: string; folder_id?: string; csv_name?: string }): Promise<DriveSyncResponse> {
  const response = await fetch(`${backendBaseUrl()}/api/drive/sync`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Backend error (${response.status})`);
  }
  return response.json();
}
