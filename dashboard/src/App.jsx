import { useState } from "react";
import "./App.css";
import Sidebar from "./components/Sidebar";
import IngestionPanel from "./components/IngestionPanel";
import ValidationPanel from "./components/ValidationPanel";
import DiagnosticPanel from "./components/DiagnosticPanel";

// Cycle réactif humain-dans-la-boucle (§2.3) : ingestion → aléa → alerte →
// déclenchement → planning proposé → validation humaine, avec la boucle
// diagnostique (§5.7) disponible sur n'importe quelle exécution choisie.
// `vue` pilote le contenu principal : soit le formulaire d'ingestion, soit
// le planning+validation+diagnostic d'une exécution choisie dans la sidebar.
function App() {
  const [vue, setVue] = useState({ type: "ingestion" });

  return (
    <div className="layout">
      <Sidebar
        vue={vue}
        onIngestion={() => setVue({ type: "ingestion" })}
        onExecutionDeclenchee={(executionId) => setVue({ type: "alerte", executionId })}
      />
      <main className="contenu">
        {vue.type === "ingestion" ? (
          <IngestionPanel />
        ) : (
          <>
            <ValidationPanel executionId={vue.executionId} />
            <DiagnosticPanel executionId={vue.executionId} />
          </>
        )}
      </main>
    </div>
  );
}

export default App;
