import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, refreshSession, setAccessToken, setSessionLostHandler } from "@/api/client";
import { keys } from "@/api/queries";
import type { AuthResponse, User } from "@/api/types";

type Status = "loading" | "authenticated" | "anonymous";

interface AuthState {
  status: Status;
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (user: User) => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUserState] = useState<User | null>(null);

  const accept = useCallback(
    (session: AuthResponse) => {
      setAccessToken(session.access_token);
      setUserState(session.user);
      qc.setQueryData(keys.me, session.user);
      setStatus("authenticated");
    },
    [qc],
  );

  const reset = useCallback(() => {
    setAccessToken(null);
    setUserState(null);
    qc.clear();
    setStatus("anonymous");
  }, [qc]);

  useEffect(() => {
    setSessionLostHandler(reset);
    // Restore the session from the httpOnly refresh cookie, if any.
    refreshSession().then((session) => (session ? accept(session) : setStatus("anonymous")));
  }, [accept, reset]);

  const value = useMemo<AuthState>(
    () => ({
      status,
      user,
      login: async (email, password) => {
        accept((await api.post<AuthResponse>("/auth/login", { email, password })).data);
      },
      register: async (name, email, password) => {
        accept((await api.post<AuthResponse>("/auth/register", { name, email, password })).data);
      },
      logout: async () => {
        try {
          await api.post("/auth/logout");
        } finally {
          reset();
        }
      },
      setUser: (u) => {
        setUserState(u);
        qc.setQueryData(keys.me, u);
      },
    }),
    [status, user, accept, reset, qc],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
