"use client";

import React, { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";

interface User {
  id: number;
  email: string;
  name: string;
  role: string;
  status: string;
  plan_type?: string;
}

interface AuthContextType {
  user: User | null;
  login: (user: User, redirectTo?: string, scope?: "user" | "admin") => void;
  logout: (options?: { redirectTo?: string; endpoint?: string; scope?: "user" | "admin" }) => Promise<void>;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [userSession, setUserSession] = useState<User | null>(null);
  const [adminSession, setAdminSession] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    let mounted = true;

    Promise.allSettled([
      api.get("/auth/me", { requireAuth: false, redirectOnUnauthorized: false, authScope: "user" }),
      api.get("/admin/me", { requireAuth: false, redirectOnUnauthorized: false, authScope: "admin" }),
    ])
      .then(([userResult, adminResult]) => {
        if (!mounted) return;
        setUserSession(userResult.status === "fulfilled" ? userResult.value as User : null);
        setAdminSession(adminResult.status === "fulfilled" ? adminResult.value as User : null);
      })
      .finally(() => {
        if (mounted) setIsLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (isLoading) return;

    const isAdminRoute = pathname.startsWith("/admin");
    const isAdminAuthRoute = pathname.startsWith("/admin/login");
    const isUserAuthRoute = pathname.startsWith("/login") || pathname.startsWith("/register");
    const user = isAdminRoute ? adminSession : userSession;

    if (isAdminRoute) {
      const isAdminUser = user?.role === "admin" || user?.role === "super_admin";
      if (!user && !isAdminAuthRoute) {
        router.push("/admin/login");
      } else if (user && !isAdminUser && !isAdminAuthRoute) {
        router.push("/admin/login");
      } else if (user && isAdminUser && isAdminAuthRoute) {
        router.push("/admin");
      }
      return;
    }

    if (!user && !isUserAuthRoute) {
      router.push("/login");
    } else if (user && isUserAuthRoute) {
      router.push("/");
    }
  }, [adminSession, userSession, pathname, isLoading, router]);

  const login = (newUser: User, redirectTo?: string, scope: "user" | "admin" = "user") => {
    if (scope === "admin") {
      setAdminSession(newUser);
      router.push(redirectTo || "/admin");
      return;
    }
    setUserSession(newUser);
    router.push(redirectTo || "/");
  };

  const logout = async (options?: { redirectTo?: string; endpoint?: string; scope?: "user" | "admin" }) => {
    const scope = options?.scope || (pathname.startsWith("/admin") ? "admin" : "user");
    const endpoint = options?.endpoint || (scope === "admin" ? "/admin/logout" : "/auth/logout");
    const redirectTo = options?.redirectTo || (scope === "admin" ? "/admin/login" : "/login");
    try {
      await api.post(endpoint, undefined, { authScope: scope });
    } catch {
      // If the session is already invalid, still clear client state.
    }
    if (scope === "admin") {
      setAdminSession(null);
    } else {
      setUserSession(null);
    }
    router.push(redirectTo);
  };

  const user = pathname.startsWith("/admin") ? adminSession : userSession;

  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
