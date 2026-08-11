/**
 * Clés de stockage de la session auth (localStorage) — module séparé, sans
 * dépendance, pour que `client.ts` (tout appel API générique) puisse lire le
 * token sans créer d'import circulaire avec `auth/service.ts`.
 */

export const AUTH_TOKEN_KEY = "prisme_auth_token";
export const AUTH_USER_KEY = "prisme_auth_user";
export const AUTH_EXPIRES_KEY = "prisme_auth_expires";

export function lireTokenStocke(): string | null {
  return localStorage.getItem(AUTH_TOKEN_KEY);
}
