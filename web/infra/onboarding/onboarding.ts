import { request } from "../http";
import type {
  OnboardingPayload,
  OnboardingResponse,
  GetOnboardingResponse,
} from "./types/onboarding-types";

export type {
  OnboardingPayload,
  OnboardingResponse,
  GetOnboardingResponse,
};

export async function completeOnboarding(payload: OnboardingPayload): Promise<OnboardingResponse> {
  return request<OnboardingResponse>("/api/onboarding/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getOnboarding(): Promise<GetOnboardingResponse> {
  return request<GetOnboardingResponse>("/api/onboarding/", {
    method: "GET",
  });
}

export async function updateOnboarding(payload: Partial<OnboardingPayload>): Promise<OnboardingResponse> {
  return request<OnboardingResponse>("/api/onboarding/", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
