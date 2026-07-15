import { useState } from "react";
import { diagnostiquerExecution } from "../api";

const LIBELLES_CAUSE = {
  code: "Code du solveur",
  donnees: "Données de production",
  specification_dsl: "Spécification DSL",
  aucune: "Aucune cause identifiée",
};

// Boucle diagnostique en direct (§5.7, PH10-T3) : rejoue le solveur réel
// via le sandbox sur le banc + les cas de référence. Lent (plusieurs
// conteneurs Docker en séquence) — un indicateur de chargement est
// indispensable, pas juste un détail cosmétique.
export default function DiagnosticPanel({ executionId }) {
  const [motif, setMotif] = useState("");
  const [diagnostic, setDiagnostic] = useState(null);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState(null);

  async function handleDiagnostiquer() {
    setEnCours(true);
    setErreur(null);
    setDiagnostic(null);
    try {
      setDiagnostic(await diagnostiquerExecution(executionId, motif));
    } catch (e) {
      setErreur(e);
    } finally {
      setEnCours(false);
    }
  }

  if (!executionId) return null;

  return (
    <section className="panel">
      <h2>Boucle diagnostique</h2>
      <p className="note">
        Rejoue le solveur réel (sandbox) sur le banc synthétique et les cas de référence —
        peut prendre plusieurs secondes.
      </p>
      <div className="validation-actions">
        <input
          type="text"
          placeholder="Motif (KPI dégradé, signalement humain…)"
          value={motif}
          onChange={(e) => setMotif(e.target.value)}
        />
        <button onClick={handleDiagnostiquer} disabled={enCours || !motif}>
          {enCours ? "Diagnostic en cours…" : "Diagnostiquer"}
        </button>
      </div>
      {erreur && <p className="erreur">{erreur.message}</p>}
      {diagnostic && (
        <div className={`diagnostic diagnostic-${diagnostic.cause}`}>
          <p>
            Cause : <strong>{LIBELLES_CAUSE[diagnostic.cause]}</strong>
          </p>
          {diagnostic.details.length > 0 && (
            <ul>
              {diagnostic.details.map((detail, i) => (
                <li key={i}>{detail}</li>
              ))}
            </ul>
          )}
          <p className="proposition">{diagnostic.proposition}</p>
          <p className="humain-decide">L'humain décide de l'action à mener.</p>
        </div>
      )}
    </section>
  );
}
