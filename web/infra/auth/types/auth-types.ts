
export type Organization = {
  organization_id: string
  name: string
  color?: string | null
}

export type User = {
  user_id: string
  email: string
  onboarding_completed?: boolean
  current_organization?: Organization | null
}

export type LoginPayload = {
  email: string
  password: string
}

export type LoginResponse = {
  access_token: string
  refresh_token?: string
  user_id: string
  email: string
}

export type RegisterPayload = {
  email: string
  password: string
  organization_name?: string
}

export type RegisterResponse = {
  detail: string
  email: string
  organization?: Organization
  needs_onboarding: boolean
}

export type UpdateProfilePayload = {
  name?: string
  onboarding_completed?: boolean
  onboarding_data?: Record<string, unknown>
}

export type UpdateProfileResponse = {
  detail: string
  user?: User
}

export type OnboardingData = Record<string, unknown>
