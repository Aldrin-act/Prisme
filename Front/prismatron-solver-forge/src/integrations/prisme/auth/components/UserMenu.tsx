/**
 * Menu utilisateur avec profil et déconnexion
 */

import { useState } from "react";
import { useAuth } from "../context";

export function UserMenu() {
  const { utilisateur, logout } = useAuth();
  const [menuOuvert, setMenuOuvert] = useState(false);

  if (!utilisateur) return null;

  const getRoleBadgeColor = (role: string) => {
    switch (role) {
      case "admin":
        return "bg-purple-100 text-purple-800";
      case "maintenant":
        return "bg-blue-100 text-blue-800";
      case "operateur":
        return "bg-green-100 text-green-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const handleLogout = async () => {
    await logout();
    window.location.href = "/login";
  };

  return (
    <div className="relative">
      <button
        onClick={() => setMenuOuvert(!menuOuvert)}
        className="flex items-center gap-3 px-4 py-2 rounded-lg hover:bg-gray-100 transition-colors"
      >
        <div className="w-10 h-10 rounded-full bg-blue-600 text-white flex items-center justify-center font-semibold">
          {utilisateur.prenom[0]}
          {utilisateur.nom[0]}
        </div>
        <div className="text-left">
          <div className="text-sm font-medium text-gray-900">
            {utilisateur.prenom} {utilisateur.nom}
          </div>
          <div className="text-xs text-gray-500">{utilisateur.email}</div>
        </div>
        <svg
          className={`w-5 h-5 text-gray-400 transition-transform ${menuOuvert ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {menuOuvert && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setMenuOuvert(false)} />
          <div className="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-lg border border-gray-200 z-20">
            <div className="p-4 border-b border-gray-200">
              <div className="font-medium text-gray-900">
                {utilisateur.prenom} {utilisateur.nom}
              </div>
              <div className="text-sm text-gray-500 mt-1">{utilisateur.email}</div>
              <div className="mt-2">
                <span
                  className={`inline-block px-2 py-1 text-xs font-medium rounded ${getRoleBadgeColor(
                    utilisateur.role,
                  )}`}
                >
                  {utilisateur.role.toUpperCase()}
                </span>
              </div>
            </div>

            <div className="p-2">
              <button
                onClick={() => {
                  setMenuOuvert(false);
                  // Navigate to profile
                  window.location.href = "/profile";
                }}
                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded"
              >
                Mon profil
              </button>
              <button
                onClick={() => {
                  setMenuOuvert(false);
                  // Navigate to settings
                  window.location.href = "/settings";
                }}
                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded"
              >
                Paramètres
              </button>
            </div>

            <div className="p-2 border-t border-gray-200">
              <button
                onClick={handleLogout}
                className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded"
              >
                Déconnexion
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
