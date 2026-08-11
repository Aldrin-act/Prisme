/**
 * Service d'authentification PRISME
 */

import { PRISME_CONFIG } from "../config";
import { PrismeAPIError } from "../client";
import { PERMISSIONS_PAR_ROLE } from "./types";
import { AUTH_TOKEN_KEY, AUTH_USER_KEY, AUTH_EXPIRES_KEY } from "./storage";
import type {
  Utilisateur,
  SessionAuth,
  CredentialsLogin,
  CredentialsRegister,
  ReponseAuth,
  ErreurAuth,
  PermissionsRole,
} from "./types";

// ============================================================================
// STORAGE (localStorage)
// ============================================================================

function sauvegarderSession(session: SessionAuth): void {
  localStorage.setItem(AUTH_TOKEN_KEY, session.token);
  localStorage.setItem(AUTH_USER_KEY, JSON.stringify(session.utilisateur));
  localStorage.setItem(AUTH_EXPIRES_KEY, session.expires_at);
}

function chargerSession(): SessionAuth | null {
  const token = localStorage.getItem(AUTH_TOKEN_KEY);
  const userJson = localStorage.getItem(AUTH_USER_KEY);
  const expiresAt = localStorage.getItem(AUTH_EXPIRES_KEY);

  if (!token || !userJson || !expiresAt) return null;

  // Vérifier expiration
  if (new Date(expiresAt) < new Date()) {
    effacerSession();
    return null;
  }

  return {
    token,
    utilisateur: JSON.parse(userJson),
    expires_at: expiresAt,
  };
}

function effacerSession(): void {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_USER_KEY);
  localStorage.removeItem(AUTH_EXPIRES_KEY);
}

// ============================================================================
// API CALLS
// ============================================================================

async function apiAuthFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const session = chargerSession();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };

  if (session) {
    headers["Authorization"] = `Bearer ${session.token}`;
  }

  try {
    const response = await fetch(`${PRISME_CONFIG.baseURL}${path}`, {
      ...options,
      headers: {
        ...headers,
        ...options?.headers,
      },
    });

    if (!response.ok) {
      // FastAPI enveloppe toujours le detail d'une HTTPException sous
      // `{"detail": ...}` — jamais au niveau racine de la réponse. Le lire
      // directement comme un `ErreurAuth` (avant ce correctif) laissait
      // `.code`/`.message` systématiquement `undefined`. `detail` est soit
      // {code, message} (ex. TOKEN_EXPIRED, voir api/routes/auth.py), soit
      // une simple chaîne (ex. "client_id inconnu" sur /register).
      let errorData: ErreurAuth = { code: "UNKNOWN", message: response.statusText };
      try {
        const body: { detail?: string | ErreurAuth } = await response.json();
        if (body.detail && typeof body.detail === "object") {
          errorData = body.detail;
        } else if (typeof body.detail === "string") {
          errorData = { code: "UNKNOWN", message: body.detail };
        }
      } catch {
        // garder le fallback statusText
      }

      throw new PrismeAPIError(errorData.message, response.status, errorData.code);
    }

    return response.json();
  } catch (error) {
    if (error instanceof PrismeAPIError) throw error;
    throw new PrismeAPIError(
      `Erreur réseau: ${error instanceof Error ? error.message : "Inconnue"}`,
    );
  }
}

// ============================================================================
// SERVICE AUTH
// ============================================================================

export const authService = {
  /**
   * Connexion avec email/password
   */
  async login(credentials: CredentialsLogin): Promise<SessionAuth> {
    const response = await apiAuthFetch<ReponseAuth>("/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    });

    sauvegarderSession(response.session);
    return response.session;
  },

  /**
   * Inscription d'un nouvel utilisateur
   */
  async register(credentials: CredentialsRegister): Promise<SessionAuth> {
    const response = await apiAuthFetch<ReponseAuth>("/auth/register", {
      method: "POST",
      body: JSON.stringify(credentials),
    });

    sauvegarderSession(response.session);
    return response.session;
  },

  /**
   * Déconnexion
   */
  async logout(): Promise<void> {
    try {
      await apiAuthFetch("/auth/logout", { method: "POST" });
    } finally {
      effacerSession();
    }
  },

  /**
   * Récupère la session courante (depuis localStorage)
   */
  getSession(): SessionAuth | null {
    return chargerSession();
  },

  /**
   * Récupère l'utilisateur courant
   */
  getUtilisateur(): Utilisateur | null {
    const session = chargerSession();
    return session?.utilisateur || null;
  },

  /**
   * Vérifie si l'utilisateur est authentifié
   */
  estAuthentifie(): boolean {
    return chargerSession() !== null;
  },

  /**
   * Récupère le token d'authentification
   */
  getToken(): string | null {
    return localStorage.getItem(AUTH_TOKEN_KEY);
  },

  /**
   * Vérifie la validité du token auprès du serveur
   */
  async verifierToken(): Promise<boolean> {
    try {
      await apiAuthFetch<{ valid: boolean }>("/auth/verify");
      return true;
    } catch {
      effacerSession();
      return false;
    }
  },

  /**
   * Rafraîchit le token
   */
  async rafraichirToken(): Promise<SessionAuth> {
    const response = await apiAuthFetch<ReponseAuth>("/auth/refresh", {
      method: "POST",
    });

    sauvegarderSession(response.session);
    return response.session;
  },

  /**
   * Récupère les permissions de l'utilisateur courant
   */
  getPermissions(): PermissionsRole | null {
    const utilisateur = this.getUtilisateur();
    if (!utilisateur) return null;
    return PERMISSIONS_PAR_ROLE[utilisateur.role];
  },

  /**
   * Vérifie si l'utilisateur a une permission spécifique
   */
  aPermission(permission: keyof PermissionsRole): boolean {
    const permissions = this.getPermissions();
    return permissions?.[permission] || false;
  },

  /**
   * Vérifie si l'utilisateur a un rôle spécifique
   */
  aRole(...roles: string[]): boolean {
    const utilisateur = this.getUtilisateur();
    return utilisateur ? roles.includes(utilisateur.role) : false;
  },

  /**
   * Change le mot de passe
   */
  async changerMotDePasse(ancienMotDePasse: string, nouveauMotDePasse: string): Promise<void> {
    await apiAuthFetch("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({
        ancien_mot_de_passe: ancienMotDePasse,
        nouveau_mot_de_passe: nouveauMotDePasse,
      }),
    });
  },

  /**
   * Demande de réinitialisation de mot de passe
   */
  async demanderReinitialisationMotDePasse(email: string): Promise<void> {
    await apiAuthFetch("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },

  /**
   * Réinitialise le mot de passe avec un token
   */
  async reinitialiserMotDePasse(token: string, nouveauMotDePasse: string): Promise<void> {
    await apiAuthFetch("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, nouveau_mot_de_passe: nouveauMotDePasse }),
    });
  },
} as const;
