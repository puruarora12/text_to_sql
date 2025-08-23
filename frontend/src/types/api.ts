export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface CreateSessionRequest {
  session_name: string;
  user_type: 'user' | 'admin';
}

export interface CreateSessionResponse {
  session_id: string;
  session_name: string;
  user_type: string;
  created_at: string;
}

export interface ConversationRequest {
  session_id: string;
  messages: ChatMessage[];
}

export interface ConversationResponse {
  session_id: string;
  messages: ChatMessage[];
  response: string;
}

export interface AssistantPayload {
  sql?: string;
  decision?: string;
  feedback?: string;
  row_count?: number;
  rows?: any[];
  type?: string;
  original_query?: string;
  requires_clarification?: boolean;
  message?: string;
  clarification_questions?: string[];
  suggested_tables?: string[];
  query_type?: string;
  action_word?: string;
  clarity_score?: number;
  vague_aspects?: string[];
}

export interface Session {
  session_id: string;
  session_name: string;
  user_type: string;
  created_at: string;
}

export interface ApiResponse<T> {
  data: T;
  message: string;
  status: number;
}
