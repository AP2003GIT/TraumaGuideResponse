export type Role = "user" | "assistant";

export type RiskLevel =
  | "standard"
  | "elevated"
  | "high"
  | "immediate";

export interface ChatMessage {
  role: Role;
  content: string;
}

export interface ChatResponse {
  reply: string;
  risk_level: RiskLevel;
  model: string | null;
  request_id: string;
  session_id: string | null;
  saved: boolean;
  disclaimer: string;
}

export interface SavedChatMessage extends ChatMessage {
  id: string;
  risk_level: RiskLevel | null;
  model: string | null;
  request_id: string;
  created_at: string;
}

export interface SavedConversation {
  session_id: string;
  messages: SavedChatMessage[];
  created_at: string;
  updated_at: string;
  expires_at: string;
  retention_days: number;
}
