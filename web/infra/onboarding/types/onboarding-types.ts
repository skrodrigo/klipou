export type OnboardingPayload = {
  organization_name: string;
  segment: string;
  color: string;
  platforms: string[];
  objective: string;
  content_type: string;
};

export type OnboardingResponse = {
  detail: string;
  onboarding_completed: boolean;
  onboarding_data: OnboardingPayload;
};

export type GetOnboardingResponse = {
  onboarding_completed: boolean;
  onboarding_data: OnboardingPayload | null;
};
