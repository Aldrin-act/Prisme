/**
 * Page de démonstration pour tester l'authentification PRISME
 */

import { useState } from "react";
import { useAuth } from "../auth";
import { useInstances, useSante } from "../hooks";

export function TestAuthPage() {
  const { utilisateur, login, logout, estAuthentifie, estChargement } = useAuth();
  const { data: sante } = useSante();
  const { data: instances, refetch: refetchInstances } = useInstances();

  const [email, setEmail] = useState("maintenant@example.com");
  const [password, setPassword] = useState("password_123");
  const [message, setMessage] = useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage("");
    try {
      await login({ email, password });
      setMessage("✅ Connexion réussie !");
      // Rafraîchir les données
      setTimeout(() => refetchInstances(), 100);
    } catch (error: any) {
      setMessage(`❌ Erreur: ${error.message}`);
    }
  };

  const handleLogout = async () => {
    await logout();
    setMessage("✅ Déconnexion réussie");
  };

  if (estChargement) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Chargement...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 py-12 px-4">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* En-tête */}
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">🧪 Test Authentification PRISME</h1>
          <p className="text-gray-600">
            Backend : <span className="font-mono text-blue-600">http://localhost:8000</span>
          </p>
        </div>

        {/* Statut Santé */}
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-xl font-bold mb-4">🏥 Santé du Système</h2>
          {sante ? (
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <span className={sante.api ? "text-2xl" : "text-2xl"}>
                  {sante.api ? "🟢" : "🔴"}
                </span>
                <span className="font-medium">API Backend</span>
                <span
                  className={`px-2 py-1 rounded text-sm ${
                    sante.api ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
                  }`}
                >
                  {sante.api ? "En ligne" : "Hors ligne"}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-2xl">{sante.sandbox_docker ? "🟢" : "🔴"}</span>
                <span className="font-medium">Sandbox Docker</span>
                <span
                  className={`px-2 py-1 rounded text-sm ${
                    sante.sandbox_docker ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
                  }`}
                >
                  {sante.sandbox_docker ? "Disponible" : "Indisponible"}
                </span>
              </div>
            </div>
          ) : (
            <p className="text-gray-500">Chargement de l'état...</p>
          )}
        </div>

        {!estAuthentifie ? (
          /* Formulaire de connexion */
          <div className="bg-white rounded-lg shadow-lg p-6">
            <h2 className="text-xl font-bold mb-4">🔐 Connexion</h2>

            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded">
              <p className="text-sm font-semibold text-blue-900 mb-2">Comptes de test :</p>
              <div className="space-y-2 text-sm">
                <div>
                  <strong>Maintenant :</strong>
                  <br />
                  Email:{" "}
                  <code className="bg-blue-100 px-2 py-1 rounded">maintenant@example.com</code>
                  <br />
                  Password: <code className="bg-blue-100 px-2 py-1 rounded">password_123</code>
                </div>
                <div className="pt-2 border-t border-blue-200">
                  <strong>Admin :</strong>
                  <br />
                  Email: <code className="bg-blue-100 px-2 py-1 rounded">admin@example.com</code>
                  <br />
                  Password: <code className="bg-blue-100 px-2 py-1 rounded">password_456</code>
                </div>
              </div>
            </div>

            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="maintenant@example.com"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Mot de passe</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="password_123"
                />
              </div>

              <button
                type="submit"
                className="w-full bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700 transition-colors font-medium"
              >
                Se connecter
              </button>
            </form>

            {message && (
              <div
                className={`mt-4 p-3 rounded ${
                  message.startsWith("✅")
                    ? "bg-green-50 text-green-700 border border-green-200"
                    : "bg-red-50 text-red-700 border border-red-200"
                }`}
              >
                {message}
              </div>
            )}
          </div>
        ) : (
          /* Utilisateur connecté */
          <>
            <div className="bg-white rounded-lg shadow-lg p-6">
              <h2 className="text-xl font-bold mb-4">👤 Utilisateur Connecté</h2>

              <div className="space-y-3">
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-full bg-blue-600 text-white flex items-center justify-center text-2xl font-bold">
                    {utilisateur?.prenom?.[0]}
                    {utilisateur?.nom?.[0]}
                  </div>
                  <div>
                    <p className="text-lg font-semibold">
                      {utilisateur?.prenom} {utilisateur?.nom}
                    </p>
                    <p className="text-gray-600">{utilisateur?.email}</p>
                  </div>
                </div>

                <div className="pt-3 border-t border-gray-200">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-gray-500">ID :</span>
                      <p className="font-mono">{utilisateur?.id}</p>
                    </div>
                    <div>
                      <span className="text-gray-500">Rôle :</span>
                      <p>
                        <span
                          className={`inline-block px-3 py-1 rounded text-sm font-medium ${
                            utilisateur?.role === "admin"
                              ? "bg-purple-100 text-purple-800"
                              : utilisateur?.role === "maintenant"
                                ? "bg-blue-100 text-blue-800"
                                : "bg-green-100 text-green-800"
                          }`}
                        >
                          {utilisateur?.role?.toUpperCase()}
                        </span>
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <button
                onClick={handleLogout}
                className="mt-6 w-full bg-red-600 text-white py-2 rounded-lg hover:bg-red-700 transition-colors"
              >
                Déconnexion
              </button>

              {message && (
                <div
                  className={`mt-4 p-3 rounded ${
                    message.startsWith("✅")
                      ? "bg-green-50 text-green-700 border border-green-200"
                      : "bg-red-50 text-red-700 border border-red-200"
                  }`}
                >
                  {message}
                </div>
              )}
            </div>

            {/* Permissions */}
            <div className="bg-white rounded-lg shadow-lg p-6">
              <h2 className="text-xl font-bold mb-4">🔑 Permissions</h2>
              <div className="grid grid-cols-2 gap-3 text-sm">
                {[
                  { key: "lire_instances", label: "Lire instances" },
                  { key: "creer_instances", label: "Créer instances" },
                  { key: "executer_solveurs", label: "Exécuter solveurs" },
                  { key: "diagnostiquer", label: "Diagnostiquer" },
                  { key: "valider_plannings", label: "Valider plannings" },
                  { key: "voir_audit", label: "Voir audit" },
                  { key: "gerer_utilisateurs", label: "Gérer utilisateurs" },
                  { key: "configurer_systeme", label: "Configurer système" },
                ].map(({ key, label }) => (
                  <div
                    key={key}
                    className={`p-3 rounded border ${
                      utilisateur?.role === "admin" ||
                      (utilisateur?.role === "maintenant" &&
                        !["gerer_utilisateurs", "configurer_systeme"].includes(key)) ||
                      (utilisateur?.role === "operateur" &&
                        [
                          "lire_instances",
                          "creer_instances",
                          "executer_solveurs",
                          "valider_plannings",
                        ].includes(key))
                        ? "bg-green-50 border-green-200 text-green-800"
                        : "bg-gray-50 border-gray-200 text-gray-500"
                    }`}
                  >
                    <span className="text-lg mr-2">
                      {utilisateur?.role === "admin" ||
                      (utilisateur?.role === "maintenant" &&
                        !["gerer_utilisateurs", "configurer_systeme"].includes(key)) ||
                      (utilisateur?.role === "operateur" &&
                        [
                          "lire_instances",
                          "creer_instances",
                          "executer_solveurs",
                          "valider_plannings",
                        ].includes(key))
                        ? "✅"
                        : "❌"}
                    </span>
                    {label}
                  </div>
                ))}
              </div>
            </div>

            {/* Instances */}
            <div className="bg-white rounded-lg shadow-lg p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold">📦 Instances ({instances?.length || 0})</h2>
                <button
                  onClick={() => refetchInstances()}
                  className="px-4 py-2 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors text-sm font-medium"
                >
                  🔄 Rafraîchir
                </button>
              </div>

              {instances && instances.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          ID
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          Client
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          Statut
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {instances.map((instance) => (
                        <tr key={instance.instance_id}>
                          <td className="px-6 py-4 text-sm font-mono">{instance.instance_id}</td>
                          <td className="px-6 py-4 text-sm">{instance.client_id}</td>
                          <td className="px-6 py-4 text-sm text-gray-500">
                            {instance.executee ? "Exécutée" : "En attente"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-gray-500 text-center py-8">Aucune instance pour le moment</p>
              )}
            </div>
          </>
        )}

        {/* Documentation */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
          <h3 className="font-bold text-blue-900 mb-2">📚 Documentation</h3>
          <ul className="space-y-1 text-sm text-blue-800">
            <li>
              • Backend API:{" "}
              <a
                href="http://localhost:8000/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                http://localhost:8000/docs
              </a>
            </li>
            <li>
              • Guide auth:{" "}
              <code className="bg-blue-100 px-2 py-1 rounded">
                src/integrations/prisme/auth/README.md
              </code>
            </li>
            <li>
              • Quickstart:{" "}
              <code className="bg-blue-100 px-2 py-1 rounded">
                src/integrations/prisme/auth/QUICKSTART.md
              </code>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
