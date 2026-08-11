/**
 * Types pour l'authentification PRISME
 */

export type RoleUtilisateur = "maintenant" | "operateur" | "admin";

export interface Utilisateur {
  id: string;
  email: string;
  nom: string;
  prenom: string;
  role: RoleUtilisateur;
  client_id?: string; // Pour les opérateurs liés à un client
  date_creation: string;
  dernier_acces?: string;
}

export interface SessionAuth {
  utilisateur: Utilisateur;
  token: string;
  expires_at: string;
}

export interface CredentialsLogin {
  email: string;
  password: string;
}

export interface CredentialsRegister {
  email: string;
  password: string;
  nom: string;
  prenom: string;
  role?: RoleUtilisateur;
  client_id?: string;
}

export interface ReponseAuth {
  session: SessionAuth;
  message: string;
}

export interface ErreurAuth {
  code: "INVALID_CREDENTIALS" | "USER_EXISTS" | "UNAUTHORIZED" | "TOKEN_EXPIRED" | "UNKNOWN";
  message: string;
}

export interface PermissionsRole {
  lire_instances: boolean;
  creer_instances: boolean;
  executer_solveurs: boolean;
  diagnostiquer: boolean;
  valider_plannings: boolean;
  gerer_utilisateurs: boolean;
  voir_audit: boolean;
  configurer_systeme: boolean;
}

export const PERMISSIONS_PAR_ROLE: Record<RoleUtilisateur, PermissionsRole> = {
  operateur: {
    lire_instances: true,
    creer_instances: true,
    executer_solveurs: true,
    diagnostiquer: false,
    valider_plannings: true,
    gerer_utilisateurs: false,
    voir_audit: false,
    configurer_systeme: false,
  },
  maintenant: {
    lire_instances: true,
    creer_instances: true,
    executer_solveurs: true,
    diagnostiquer: true,
    valider_plannings: true,
    gerer_utilisateurs: false,
    voir_audit: true,
    configurer_systeme: false,
  },
  admin: {
    lire_instances: true,
    creer_instances: true,
    executer_solveurs: true,
    diagnostiquer: true,
    valider_plannings: true,
    gerer_utilisateurs: true,
    voir_audit: true,
    configurer_systeme: true,
  },
};
