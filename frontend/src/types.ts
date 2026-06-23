export type Role = "user" | "assistant";
export type UserRole = "user" | "admin";

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

export interface AuthenticatedUser {
  user_id: string;
  email: string;
  display_name: string;
  role: UserRole;
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  user: AuthenticatedUser;
}

export interface PasswordResetRequestResponse {
  accepted: boolean;
  dev_reset_token: string | null;
}

export interface SavedChatMessage extends ChatMessage {
  id: string;
  risk_level: RiskLevel | null;
  model: string | null;
  request_id: string;
  created_at: string;
}

export interface SavedConversation {
  user_id: string;
  session_id: string;
  messages: SavedChatMessage[];
  created_at: string;
  updated_at: string;
  expires_at: string;
  retention_days: number;
}

export interface SavedConversationSummary {
  user_id: string;
  session_id: string;
  title: string;
  last_message_preview: string;
  message_count: number;
  created_at: string;
  updated_at: string;
  expires_at: string;
  retention_days: number;
}

export interface SavedConversationList {
  conversations: SavedConversationSummary[];
  max_saved_chats: number;
  retention_days: number;
}

export interface AccountExport {
  user: AuthenticatedUser;
  conversations: SavedConversation[];
  exported_at: string;
}

export interface DependencyStatus {
  gateway: string;
  safety_service: string;
  chat_service: string;
  save_service: string;
}

export interface AdminSummary {
  users: number;
  conversations: number;
  messages: number;
  expiring_soon: number;
  retention_days: number;
  max_saved_chats: number;
  generated_at: string;
}

export interface AdminDashboard {
  dependencies: DependencyStatus;
  storage: AdminSummary;
}
