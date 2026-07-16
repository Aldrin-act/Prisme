import { useState } from "react";
import "./App.css";
import Sidebar from "./components/Sidebar";
import IngestionPanel from "./components/IngestionPanel";
import ValidationPanel from "./components/ValidationPanel";
import DiagnosticPanel from "./components/DiagnosticPanel";

// Cycle réactif humain-dans-la-boucle (§2.3) : ingestion → exécution →
// planning proposé → validation humaine, avec la boucle diagnostique (§5.7)
// disponible sur n'importe quelle exécution choisie. Un aléa atelier
// (panne, retard...) n'a pas de fil dédié : il se traduit dans les
// contraintes de l'instance, ré-ingérée puis réexécutée — le processus
// varie d'un client à l'autre, donc pas figé ici.
// `onglet` pilote le contenu principal, `executionId` l'exécution
// actuellement sélectionnée (produite par l'onglet Ingestion, réutilisée
// par l'onglet Diagnostic).
function App() {
  const [onglet, setOnglet] = useState("ingestion");
  const [executionId, setExecutionId] = useState(null);

  function handleExecutionDeclenchee(id) {
    setExecutionId(id);
    setOnglet("planning");
  }

  return (
    <div className="layout">
      <Sidebar onglet={onglet} onChangerOnglet={setOnglet} />
      <main className="contenu">
        {onglet === "ingestion" && <IngestionPanel onExecutionDeclenchee={handleExecutionDeclenchee} />}
        {onglet === "planning" && <ValidationPanel executionId={executionId} />}
        {onglet === "diagnostic" &&
          (executionId ? (
            <DiagnosticPanel executionId={executionId} />
          ) : (
            <section className="panel">
              <h2>Boucle diagnostique</h2>
              <p className="vide">Déclenche d'abord une exécution depuis l'onglet Ingestion.</p>
            </section>
          ))}
      </main>
    </div>
  );
}

export default App;
