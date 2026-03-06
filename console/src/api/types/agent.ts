export interface AgentRequest {
  input: unknown;
  session_id?: string | null;
  user_id?: string | null;
  channel?: string | null;
  [key: string]: unknown;
}

export interface AgentsRunningConfig {
  max_iters: number;
  max_input_length: number;
}

export interface BotProfileConfig {
  key: string;
  name: string;
  enabled: boolean;
  description: string;
  identity_prompt: string;
}

export interface BotProfilesConfig {
  enabled: boolean;
  default_bot: string;
  profiles: BotProfileConfig[];
  channel_bindings: Record<string, string>;
}
