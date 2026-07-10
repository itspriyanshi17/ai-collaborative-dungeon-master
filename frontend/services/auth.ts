import { apiFetch } from "@/services/api";
import type { AuthResponse, AuthUser, LoginPayload, RegisterPayload } from "@/types/auth";

export function registerUser(payload: RegisterPayload) {
  return apiFetch<AuthResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function loginUser(payload: LoginPayload) {
  return apiFetch<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function refreshSession() {
  return apiFetch<AuthResponse>("/api/auth/refresh", {
    method: "POST"
  });
}

export function fetchCurrentUser(accessToken: string) {
  return apiFetch<AuthUser>("/api/auth/me", {
    method: "GET",
    accessToken
  });
}

export function logoutUser(accessToken: string | null) {
  return apiFetch<{ message: string }>("/api/auth/logout", {
    method: "POST",
    accessToken
  });
}
