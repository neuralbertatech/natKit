import { writable } from "svelte/store";

export interface SessionUser {
  username: string;
  display_name: string;
  is_admin: boolean;
}

export interface AuthSession {
  authenticated: boolean;
  bootstrap_required: boolean;
  bootstrap_mode: "password" | "auto_admin";
  user: SessionUser | null;
}

export interface ManagedUser {
  username: string;
  display_name: string;
  is_admin: boolean;
  enabled: boolean;
  shared_compute_access: boolean;
  created_at_us: number;
  updated_at_us: number;
  password_updated_at_us: number;
  last_login_at_us: number;
}

export const authSession = writable<AuthSession | null>(null);

async function readJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  const data = text ? (JSON.parse(text) as T & { message?: string }) : ({} as T & { message?: string });
  if (!response.ok) {
    throw new Error(data.message || `Request failed with status ${response.status}`);
  }
  return data;
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  return readJson<T>(response);
}

export async function refreshSession(): Promise<AuthSession> {
  const session = await apiRequest<AuthSession>("/api/auth/session", {
    method: "GET",
  });
  authSession.set(session);
  return session;
}

export async function login(username: string, password: string): Promise<AuthSession> {
  await apiRequest("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  return refreshSession();
}

export async function bootstrapAdmin(args: {
  username: string;
  display_name: string;
  password: string;
  bootstrap_password?: string;
}): Promise<AuthSession> {
  await apiRequest("/api/auth/bootstrap", {
    method: "POST",
    body: JSON.stringify(args),
  });
  return refreshSession();
}

export async function logout(): Promise<AuthSession> {
  await apiRequest("/api/auth/logout", {
    method: "POST",
    body: JSON.stringify({}),
  });
  return refreshSession();
}

export async function listUsers(): Promise<ManagedUser[]> {
  const response = await apiRequest<{ users: ManagedUser[] }>("/api/admin/users", {
    method: "GET",
  });
  return response.users;
}

export async function createUser(payload: {
  username: string;
  display_name: string;
  password: string;
  is_admin: boolean;
  enabled: boolean;
  shared_compute_access: boolean;
}): Promise<void> {
  await apiRequest("/api/admin/users/create", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateUser(payload: {
  username: string;
  display_name?: string;
  password?: string;
  is_admin?: boolean;
  enabled?: boolean;
  shared_compute_access?: boolean;
}): Promise<void> {
  await apiRequest("/api/admin/users/update", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deleteUser(username: string): Promise<void> {
  await apiRequest("/api/admin/users/delete", {
    method: "POST",
    body: JSON.stringify({ username }),
  });
}
