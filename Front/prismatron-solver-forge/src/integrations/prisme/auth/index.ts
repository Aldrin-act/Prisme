/**
 * Module d'authentification PRISME - Export centralisé
 */

// Service
export { authService } from "./service";

// Context & Hook
export { AuthProvider, useAuth, type AuthContextValue } from "./context";

// Types
export * from "./types";

// Composants
export { LoginForm } from "./components/LoginForm";
export { ProtectedRoute } from "./components/ProtectedRoute";
export { UserMenu } from "./components/UserMenu";
