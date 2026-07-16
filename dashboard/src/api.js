// Client fetch minimal pour l'API PRISME — pas de bibliothèque HTTP, pas de
// temps réel : tout passe par polling (voir les composants qui appellent ces
// fonctions avec setInterval).

const BASE_URL = "http://localhost:8000";

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!reponse.ok) {
    const corps = await reponse.json().catch(() => ({}));
    const erreur = new Error(corps.detail ? JSON.stringify(corps.detail) : reponse.statusText);
    erreur.status = reponse.status;
    throw erreur;
  }
  if (reponse.status === 204) return null;
  return reponse.json();
}

export function ingererInstance(clientId, instance) {
  return requete(`/ingestion/${clientId}`, {
    method: "POST",
    body: JSON.stringify(instance),
  });
}

export function declencherExecution(instanceId, clientId) {
  return requete(`/execution/${instanceId}?client_id=${encodeURIComponent(clientId)}`, { method: "POST" });
}

export function obtenirPlanning(executionId) {
  return requete(`/planning/${executionId}`);
}

export function obtenirDecision(executionId) {
  return requete(`/executions/${executionId}/decision`).catch((erreur) => {
    if (erreur.status === 404) return null;
    throw erreur;
  });
}

export function enregistrerDecision(executionId, decision, commentaire) {
  return requete(`/executions/${executionId}/decision`, {
    method: "POST",
    body: JSON.stringify({ decision, commentaire: commentaire || null }),
  });
}

export function diagnostiquerExecution(executionId, motifDeclenchement) {
  return requete(`/diagnostics/${executionId}`, {
    method: "POST",
    body: JSON.stringify({ motif_declenchement: motifDeclenchement }),
  });
}
