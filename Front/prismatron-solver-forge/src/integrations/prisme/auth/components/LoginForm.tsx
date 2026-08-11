/**
 * Formulaire de connexion
 */

import { useState } from "react";
import { useAuth } from "../context";
import { PrismeAPIError } from "../../client";

export function LoginForm() {
  const { login, estChargement } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [erreur, setErreur] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErreur("");

    try {
      await login({ email, password });
    } catch (error) {
      if (error instanceof PrismeAPIError) {
        switch (error.detail) {
          case "INVALID_CREDENTIALS":
            setErreur("Email ou mot de passe incorrect");
            break;
          case "UNAUTHORIZED":
            setErreur("Accès non autorisé");
            break;
          default:
            setErreur(error.message);
        }
      } else {
        setErreur("Erreur de connexion");
      }
    }
  };

  const remplirFormulaire = (email: string, password: string) => {
    setEmail(email);
    setPassword(password);
    setErreur("");
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">PRISME</h1>
          <p className="text-gray-600 mt-2">Connexion Maintenant</p>
        </div>

        {/* Comptes de test */}
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm font-semibold text-blue-900 mb-3">Comptes de test disponibles :</p>
          <div className="space-y-3">
            {/* Compte Maintenant */}
            <div className="bg-white p-3 rounded border border-blue-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-blue-700">MAINTENANT</span>
                <button
                  type="button"
                  onClick={() => remplirFormulaire("maintenant@example.com", "password_123")}
                  className="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 transition-colors"
                >
                  Utiliser
                </button>
              </div>
              <div className="text-xs text-gray-600 space-y-1">
                <div>
                  <span className="font-medium">Email:</span>{" "}
                  <code className="bg-gray-100 px-2 py-0.5 rounded">maintenant@example.com</code>
                </div>
                <div>
                  <span className="font-medium">Password:</span>{" "}
                  <code className="bg-gray-100 px-2 py-0.5 rounded">password_123</code>
                </div>
              </div>
            </div>

            {/* Compte Admin */}
            <div className="bg-white p-3 rounded border border-blue-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-purple-700">ADMIN</span>
                <button
                  type="button"
                  onClick={() => remplirFormulaire("admin@example.com", "password_456")}
                  className="text-xs bg-purple-600 text-white px-3 py-1 rounded hover:bg-purple-700 transition-colors"
                >
                  Utiliser
                </button>
              </div>
              <div className="text-xs text-gray-600 space-y-1">
                <div>
                  <span className="font-medium">Email:</span>{" "}
                  <code className="bg-gray-100 px-2 py-0.5 rounded">admin@example.com</code>
                </div>
                <div>
                  <span className="font-medium">Password:</span>{" "}
                  <code className="bg-gray-100 px-2 py-0.5 rounded">password_456</code>
                </div>
              </div>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="maintenant@example.com"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
              Mot de passe
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="••••••••"
            />
          </div>

          {erreur && (
            <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
              {erreur}
            </div>
          )}

          <button
            type="submit"
            disabled={estChargement}
            className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {estChargement ? "Connexion..." : "Se connecter"}
          </button>
        </form>

        <div className="mt-6 text-center">
          <a href="/forgot-password" className="text-sm text-blue-600 hover:text-blue-700">
            Mot de passe oublié ?
          </a>
        </div>
      </div>
    </div>
  );
}
