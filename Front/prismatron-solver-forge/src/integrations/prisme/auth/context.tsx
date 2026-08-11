/**
 * Context et Provider pour l'authentification PRISME
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { authService } from "./service";
import type {
  Utilisateur,
  SessionAuth,
  CredentialsLogin,
  CredentialsRegister,
  PermissionsRole,
} from "./types";

// ============================================================================
// TYPES
// ============================================================================

interface AuthContextValue {
  utilisateur: Utilisateur | null;
  session: SessionAuth | null;
  estAuthentifie: boolean;
  estChargement: boolean;
  login: (credentials: CredentialsLogin) => Promise<void>;
  register: (credentials: CredentialsRegister) => Promise<void>;
  logout: () => Promise<void>;
  rafraichir: () => Promise<void>;
  aPermission: (permission: keyof PermissionsRole) => boolean;
  aRole: (...roles: string[]) => boolean;
}

// ============================================================================
// CONTEXT
// ============================================================================

const AuthContext = createContext<AuthContextValue | null>(null);

// ============================================================================
// PROVIDER
// ============================================================================

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<SessionAuth | null>(null);
  const [estChargement, setEstChargement] = useState(true);

  // Charger la session au montage
  useEffect(() => {
    const sessionSauvegardee = authService.getSession();
    if (sessionSauvegardee) {
      setSession(sessionSauvegardee);
      // Vérifier la validité du token
      authService.verifierToken().catch(() => {
        setSession(null);
      });
    }
    setEstChargement(false);
  }, []);

  // Auto-refresh du token avant expiration
  useEffect(() => {
    if (!session) return;

    const expiresAt = new Date(session.expires_at);
    const now = new Date();
    const tempsAvantExpiration = expiresAt.getTime() - now.getTime();

    // Rafraîchir 5 minutes avant expiration
    const delaiRefresh = Math.max(0, tempsAvantExpiration - 5 * 60 * 1000);

    const timer = setTimeout(() => {
      authService
        .rafraichirToken()
        .then((nouvelleSession) => {
          setSession(nouvelleSession);
        })
        .catch(() => {
          setSession(null);
        });
    }, delaiRefresh);

    return () => clearTimeout(timer);
  }, [session]);

  const login = useCallback(async (credentials: CredentialsLogin) => {
    setEstChargement(true);
    try {
      const nouvelleSession = await authService.login(credentials);
      setSession(nouvelleSession);
    } finally {
      setEstChargement(false);
    }
  }, []);

  const register = useCallback(async (credentials: CredentialsRegister) => {
    setEstChargement(true);
    try {
      const nouvelleSession = await authService.register(credentials);
      setSession(nouvelleSession);
    } finally {
      setEstChargement(false);
    }
  }, []);

  const logout = useCallback(async () => {
    setEstChargement(true);
    try {
      await authService.logout();
    } finally {
      setSession(null);
      setEstChargement(false);
    }
  }, []);

  const rafraichir = useCallback(async () => {
    try {
      const nouvelleSession = await authService.rafraichirToken();
      setSession(nouvelleSession);
    } catch {
      setSession(null);
    }
  }, []);

  const aPermission = useCallback(
    (permission: keyof PermissionsRole) => {
      return authService.aPermission(permission);
    },
    [session],
  );

  const aRole = useCallback(
    (...roles: string[]) => {
      return authService.aRole(...roles);
    },
    [session],
  );

  const value: AuthContextValue = {
    utilisateur: session?.utilisateur || null,
    session,
    estAuthentifie: !!session,
    estChargement,
    login,
    register,
    logout,
    rafraichir,
    aPermission,
    aRole,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ============================================================================
// HOOK
// ============================================================================

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth doit être utilisé dans un AuthProvider");
  }
  return context;
}

// ============================================================================
// EXPORTS
// ============================================================================

export type { AuthContextValue };
