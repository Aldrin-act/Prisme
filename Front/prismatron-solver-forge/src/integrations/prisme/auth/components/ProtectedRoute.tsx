/**
 * Composant de protection de route
 */

import { ReactNode } from "react";
import { Navigate } from "@tanstack/react-router";
import { useAuth } from "../context";
import type { RoleUtilisateur, PermissionsRole } from "../types";

interface ProtectedRouteProps {
  children: ReactNode;
  requiredRole?: RoleUtilisateur | RoleUtilisateur[];
  requiredPermission?: keyof PermissionsRole;
  redirectTo?: string;
  fallback?: ReactNode;
}

export function ProtectedRoute({
  children,
  requiredRole,
  requiredPermission,
  redirectTo = "/login",
  fallback,
}: ProtectedRouteProps) {
  const { estAuthentifie, estChargement, aRole, aPermission } = useAuth();

  // Chargement initial
  if (estChargement) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
          <p className="mt-4 text-gray-600">Vérification...</p>
        </div>
      </div>
    );
  }

  // Pas authentifié
  if (!estAuthentifie) {
    return <Navigate to={redirectTo} />;
  }

  // Vérifier le rôle requis
  if (requiredRole) {
    const roles = Array.isArray(requiredRole) ? requiredRole : [requiredRole];
    if (!aRole(...roles)) {
      return (
        fallback || (
          <div className="min-h-screen flex items-center justify-center">
            <div className="text-center">
              <h1 className="text-4xl font-bold text-red-600">403</h1>
              <p className="mt-4 text-gray-600">Accès refusé</p>
              <p className="mt-2 text-sm text-gray-500">
                Vous n'avez pas les permissions nécessaires
              </p>
            </div>
          </div>
        )
      );
    }
  }

  // Vérifier la permission requise
  if (requiredPermission && !aPermission(requiredPermission)) {
    return (
      fallback || (
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <h1 className="text-4xl font-bold text-red-600">403</h1>
            <p className="mt-4 text-gray-600">Accès refusé</p>
            <p className="mt-2 text-sm text-gray-500">Permission "{requiredPermission}" requise</p>
          </div>
        </div>
      )
    );
  }

  return <>{children}</>;
}
