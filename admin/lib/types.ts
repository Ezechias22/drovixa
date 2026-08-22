export type AdminUser = {
  id: string;
  email: string;
  name: string;
  status: string;
  email_verified: boolean;
  country_code?: string | null;
  language_code?: string | null;
  roles: string[];
  devices?: number;
  created_at?: string;
};

export type FeatureFlag = {
  key: string;
  description: string;
  enabled: boolean;
  rollout_percentage: number;
  rules: Record<string, unknown>;
  updated_at: string;
};

export type RemoteConfig = {
  key: string;
  value: unknown;
  description: string;
  is_public: boolean;
  updated_at: string;
};

export type PageMeta = { page: number; limit: number; total: number; pages: number };
