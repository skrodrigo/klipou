export type OnboardingData = {
  content_type?: string;
  platforms?: string[];
  objective?: string;
  language?: string;
  frequency?: string;
};

export type User = {
  user_id: string
  email: string
  organization_id?: string
  organization?: Organization
  onboarding_completed?: boolean
  onboarding_data?: OnboardingData
};

export type LoginPayload = {
  email: string;
  password: string;
};

export type LoginResponse = {
  detail: string;
  email?: string;
};

export type RegisterPayload = {
  email: string;
  password: string;
  organization_name?: string;
};

export type Organization = {
  organization_id: string;
  name: string;
  color: string;
  plan: "starter" | "pro" | "business";
  credits_available: number;
};

export type RegisterResponse = {
  detail: string;
  email?: string;
  organization?: Organization;
};

export type UpdateProfilePayload = {
  email?: string;
  onboarding_completed?: boolean;
  onboarding_data?: OnboardingData;
};

export type UpdateProfileResponse = {
  detail: string;
  user: User;
};
