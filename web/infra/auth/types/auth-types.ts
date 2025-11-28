export type User = {
  id: number;
  email: string;
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
};

export type RegisterResponse = {
  detail: string;
  email?: string;
};
