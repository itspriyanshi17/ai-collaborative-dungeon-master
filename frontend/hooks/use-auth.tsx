"use client";

import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { loginUser, logoutUser, refreshSession, registerUser } from "@/services/auth";
import type { AuthUser, LoginPayload, RegisterPayload } from "@/types/auth";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  user: AuthUser | null;
  accessToken: string | null;
  status: AuthStatus;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  useEffect(() => {
    let isMounted = true;

    refreshSession()
      .then((session) => {
        if (!isMounted) {
          return;
        }
        setUser(session.user);
        setAccessToken(session.access_token);
        setStatus("authenticated");
      })
      .catch(() => {
        if (!isMounted) {
          return;
        }
        setUser(null);
        setAccessToken(null);
        setStatus("unauthenticated");
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const login = useCallback(
    async (payload: LoginPayload) => {
      const session = await loginUser(payload);
      setUser(session.user);
      setAccessToken(session.access_token);
      setStatus("authenticated");
      router.push("/");
    },
    [router]
  );

  const register = useCallback(
    async (payload: RegisterPayload) => {
      const session = await registerUser(payload);
      setUser(session.user);
      setAccessToken(session.access_token);
      setStatus("authenticated");
      router.push("/");
    },
    [router]
  );

  const logout = useCallback(async () => {
    await logoutUser(accessToken).catch(() => undefined);
    setUser(null);
    setAccessToken(null);
    setStatus("unauthenticated");
    router.push("/auth/login");
  }, [accessToken, router]);

  const value = useMemo(
    () => ({ user, accessToken, status, login, register, logout }),
    [accessToken, login, logout, register, status, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }
  return value;
}
