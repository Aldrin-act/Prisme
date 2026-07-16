import { useEffect, useState } from "react";
import { enregistrerDecision, obtenirDecision, obtenirPlanning } from "../api";
import GanttChart from "./GanttChart";

// Validation humaine (§2.3 étape 6, PH10-T2) : présente le planning proposé,
// n'applique jamais rien automatiquement — la décision (acceptée/refusée)
// est le seul geste qui compte, toujours explicite.
export default function ValidationPanel({ executionId }) {
  const [planning, setPlanning] = useState(null);
  const [decision, setDecision] = useState(null);
  const [commentaire, setCommentaire] = useState("");
  const [erreur, setErreur] = useState(null);
  const [enCours, setEnCours] = useState(false);

  useEffect(() => {
    if (!executionId) return;
    setPlanning(null);
    setDecision(null);
    setErreur(null);
    obtenirPlanning(executionId).then(setPlanning).catch(setErreur);
    obtenirDecision(executionId).then(setDecision).catch(setErreur);
  }, [executionId]);

  async function handleDecision(valeur) {
    setEnCours(true);
    setErreur(null);
    try {
      await enregistrerDecision(executionId, valeur, commentaire);
      setDecision(await obtenirDecision(executionId));
    } catch (e) {
      setErreur(e);
    } finally {
      setEnCours(false);
    }
  }

  if (!executionId) {
    return (
      <section className="panel">
        <h2>Planning proposé</h2>
        <p className="vide">Déclenche une exécution depuis l'onglet Ingestion pour voir un planning ici.</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <h2>Planning proposé</h2>
      {erreur && <p className="erreur">{erreur.message}</p>}
      {planning ? <GanttChart planning={planning} /> : <p>Chargement…</p>}

      {decision ? (
        <p className={`decision decision-${decision.decision}`}>
          Décision : <strong>{decision.decision}</strong> ({decision.horodatage})
          {decision.commentaire && ` — ${decision.commentaire}`}
        </p>
      ) : (
        <div className="validation-actions">
          <input
            type="text"
            placeholder="Commentaire (optionnel)"
            value={commentaire}
            onChange={(e) => setCommentaire(e.target.value)}
          />
          <button onClick={() => handleDecision("acceptee")} disabled={enCours}>
            Accepter
          </button>
          <button onClick={() => handleDecision("refusee")} disabled={enCours}>
            Refuser
          </button>
        </div>
      )}
    </section>
  );
}
