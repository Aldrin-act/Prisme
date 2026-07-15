import { useEffect, useState } from "react";
import { declencherRecalcul, listerAlertes } from "../api";

const LIBELLES_ALEA = {
  panne: "Panne machine",
  commande_urgente: "Commande urgente",
  retard: "Retard",
};

// Alertes d'aléa (§2.3, PH10-T1) : le système ne fait qu'afficher — c'est
// toujours un humain qui clique "Déclencher le recalcul", jamais automatique.
export default function AlertList({ executionSelectionnee, onExecutionDeclenchee }) {
  const [alertes, setAlertes] = useState([]);
  const [enCours, setEnCours] = useState(null);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    const rafraichir = () => listerAlertes().then(setAlertes).catch(setErreur);
    rafraichir();
    const intervalle = setInterval(rafraichir, 3000);
    return () => clearInterval(intervalle);
  }, []);

  async function handleDeclencher(alerteId) {
    setEnCours(alerteId);
    setErreur(null);
    try {
      const { execution_id: executionId } = await declencherRecalcul(alerteId);
      onExecutionDeclenchee(executionId);
      const fraiches = await listerAlertes();
      setAlertes(fraiches);
    } catch (e) {
      setErreur(e);
    } finally {
      setEnCours(null);
    }
  }

  return (
    <section className="panel">
      <h2>Alertes</h2>
      {erreur && <p className="erreur">{erreur.message}</p>}
      {alertes.length === 0 && <p className="vide">Aucune alerte pour l'instant.</p>}
      <ul className="liste-alertes">
        {alertes.map((alerte) => (
          <li
            key={alerte.id}
            className={alerte.execution_id === executionSelectionnee ? "selectionnee" : ""}
          >
            <div className="alerte-entete">
              <span className={`badge badge-${alerte.type_alea}`}>{LIBELLES_ALEA[alerte.type_alea]}</span>
              <span className={`statut statut-${alerte.statut}`}>{alerte.statut}</span>
            </div>
            <p>{alerte.description}</p>
            <p className="horodatage">{alerte.horodatage}</p>
            {alerte.statut === "nouvelle" ? (
              <button onClick={() => handleDeclencher(alerte.id)} disabled={enCours === alerte.id}>
                {enCours === alerte.id ? "Déclenchement…" : "Déclencher le recalcul"}
              </button>
            ) : (
              <button onClick={() => onExecutionDeclenchee(alerte.execution_id)}>
                Voir le planning proposé
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
