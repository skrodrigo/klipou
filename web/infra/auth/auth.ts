import { request } from "../http";
import type {
  User,
  LoginPayload,
  LoginResponse,
  RegisterPayload,
  RegisterResponse,
  UpdateProfilePayload,
  UpdateProfileResponse,
  OnboardingData,
  Organization,
} from "./types/auth-types";

export type {
  User,
  LoginPayload,
  LoginResponse,
  RegisterPayload,
  RegisterResponse,
  UpdateProfilePayload,
  UpdateProfileResponse,
  OnboardingData,
  Organization,
};

export async function login(payload: LoginPayload): Promise<LoginResponse> {
  return request<LoginResponse>("/api/auth/login/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function register(payload: RegisterPayload): Promise<RegisterResponse> {
  return request<RegisterResponse>("/api/auth/register/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function logout(): Promise<{ detail: string }> {
  return request<{ detail: string }>("/api/auth/logout/", {
    method: "POST",
  });
}

export async function getSession(): Promise<User | null> {
  try {
    return await request<User>("/api/auth/me/");
  } catch {
    return null;
  }
}

export async function updateProfile(payload: UpdateProfilePayload): Promise<UpdateProfileResponse> {
  return request<UpdateProfileResponse>("/api/auth/me/update/", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
