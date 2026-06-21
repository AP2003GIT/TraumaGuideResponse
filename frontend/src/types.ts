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
  disclaimer: string;
}
