import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

import type { ApiErrorBody, AuthResponse } from "./types";

// The access token lives only in memory; the refresh token is an httpOnly cookie.
let accessToken: string | null = null;
let onSessionLost: (() => void) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function setSessionLostHandler(fn: () => void) {
  onSessionLost = fn;
}

export const api = axios.create({ baseURL: "/api/v1", withCredentials: true });

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

// One refresh in flight at a time; concurrent 401s wait for it.
let refreshing: Promise<AuthResponse | null> | null = null;

export function refreshSession(): Promise<AuthResponse | null> {
  refreshing ??= axios
    .post<AuthResponse>("/api/v1/auth/refresh", null, { withCredentials: true })
    .then((r) => {
      setAccessToken(r.data.access_token);
      return r.data;
    })
    .catch(() => {
      setAccessToken(null);
      return null;
    })
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined;
    const isAuthCall = config?.url?.startsWith("/auth/");
    if (error.response?.status === 401 && config && !config._retried && !isAuthCall) {
      config._retried = true;
      const session = await refreshSession();
      if (session) return api(config);
      onSessionLost?.();
    }
    return Promise.reject(error);
  },
);

/** Human message from any API error. */
export function errorMessage(error: unknown, fallback = "Something went wrong. Please try again."): string {
  if (axios.isAxiosError(error)) {
    const body = error.response?.data as Partial<ApiErrorBody> | undefined;
    if (body?.error?.message) return body.error.message;
    if (!error.response) return "Can't reach Spendzer right now. Check your connection.";
  }
  return fallback;
}

export function errorCode(error: unknown): string | undefined {
  if (axios.isAxiosError(error)) {
    return (error.response?.data as Partial<ApiErrorBody> | undefined)?.error?.code;
  }
  return undefined;
}
