import { useState } from "react";
import "./App.css";
import AlertList from "./components/AlertList";
import ValidationPanel from "./components/ValidationPanel";
import DiagnosticPanel from "./components/DiagnosticPanel";

// Cycle réactif humain-dans-la-boucle (§2.3) : aléa → alerte → déclenchement
// → planning proposé → validation humaine, avec la boucle diagnostique
// (§5.7) disponible sur n'importe quelle exécution choisie.
function App() {
  const [executionId, setExecutionId] = useState(null);

  return (
    <div className="app">
      <header>
        <h1>PRISME — Tableau de bord</h1>
        <p className="sous-titre">Le système alerte, l'humain décide.</p>
      </header>
      <main>
        <AlertList executionSelectionnee={executionId} onExecutionDeclenchee={setExecutionId} />
        <ValidationPanel executionId={executionId} />
        <DiagnosticPanel executionId={executionId} />
      </main>
    </div>
  );
}

export default App;
