import { useState } from "react";
import { ingererInstance, leverAlerte } from "../api";

// Exemples de démo, copiés depuis dsl/examples/valid/ pour peuplement rapide
// du formulaire — dsl/examples/ reste la source de vérité pour les tests,
// ceci n'est qu'une commodité d'UI, pas une donnée testée contre le schéma.
const EXEMPLES = {
  "Atelier 3 tâches": {
    taches: [{ id: "T1", nom: "Decoupe" }, { id: "T2", nom: "Assemblage" }, { id: "T3", nom: "Controle" }],
    ressources: [{ id: "M1", nom: "Decoupeuse" }, { id: "M2", nom: "Poste assemblage" }],
    contraintes: [
      { type: "precedence", avant: "T1", apres: "T2" },
      { type: "precedence", avant: "T2", apres: "T3" },
      { type: "compatibilite_machine_tache", tache: "T1", ressource: "M1", duree: 30 },
      { type: "compatibilite_machine_tache", tache: "T2", ressource: "M1", duree: 45 },
      { type: "compatibilite_machine_tache", tache: "T2", ressource: "M2", duree: 45 },
      { type: "compatibilite_machine_tache", tache: "T3", ressource: "M2", duree: 15 },
    ],
    objectifs: [{ type: "minimiser_makespan" }],
  },
};

const TYPES_ALEA = ["panne", "commande_urgente", "retard"];

// Ingestion (§5.1, §5.5, §6.7) + création d'alerte — pour que tout le cycle
// human-in-the-loop (§2.3) soit utilisable depuis le navigateur, sans curl.
// `AlertList` interroge /alertes toutes les 3s de son côté : pas besoin de
// forcer un rafraîchissement immédiat ici, la nouvelle alerte apparaît seule.
export default function IngestionPanel() {
  const [clientId, setClientId] = useState("demo");
  const [payloadTexte, setPayloadTexte] = useState(JSON.stringify(EXEMPLES["Atelier 3 tâches"], null, 2));
  const [instance, setInstance] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [enCours, setEnCours] = useState(false);

  const [typeAlea, setTypeAlea] = useState(TYPES_ALEA[0]);
  const [description, setDescription] = useState("");
  const [alerteCreee, setAlerteCreee] = useState(false);

  function chargerExemple(nom) {
    setPayloadTexte(JSON.stringify(EXEMPLES[nom], null, 2));
    setInstance(null);
    setAlerteCreee(false);
    setErreur(null);
  }

  async function handleIngerer() {
    setErreur(null);
    setInstance(null);
    setAlerteCreee(false);
    let payload;
    try {
      payload = JSON.parse(payloadTexte);
    } catch {
      setErreur(new Error("JSON invalide : vérifie la syntaxe du payload."));
      return;
    }
    setEnCours(true);
    try {
      const resultat = await ingererInstance(clientId, payload);
      setInstance(resultat);
    } catch (e) {
      setErreur(e);
    } finally {
      setEnCours(false);
    }
  }

  async function handleLeverAlerte() {
    setErreur(null);
    setEnCours(true);
    try {
      await leverAlerte(instance.instance_id, clientId, typeAlea, description);
      setAlerteCreee(true);
    } catch (e) {
      setErreur(e);
    } finally {
      setEnCours(false);
    }
  }

  return (
    <section className="panel">
      <h2>Ingestion (§6.7)</h2>
      <div className="ingestion-form">
        <label>
          Client
          <input type="text" value={clientId} onChange={(e) => setClientId(e.target.value)} />
        </label>
        <label>
          Exemples
          <select onChange={(e) => chargerExemple(e.target.value)} defaultValue="">
            <option value="" disabled>
              Charger un exemple…
            </option>
            {Object.keys(EXEMPLES).map((nom) => (
              <option key={nom} value={nom}>
                {nom}
              </option>
            ))}
          </select>
        </label>
        <textarea
          rows={10}
          value={payloadTexte}
          onChange={(e) => {
            setPayloadTexte(e.target.value);
            setInstance(null);
            setAlerteCreee(false);
          }}
        />
        <button onClick={handleIngerer} disabled={enCours}>
          {enCours ? "Ingestion…" : "Ingérer l'instance"}
        </button>
      </div>

      {erreur && <p className="erreur">{erreur.message}</p>}

      {instance && (
        <div className="ingestion-resultat">
          <p>
            Instance <code>{instance.instance_id}</code> — structure :{" "}
            <code>{instance.structure_contraintes}</code>
          </p>

          {alerteCreee ? (
            <p className="note">Alerte créée — visible dans la liste ci-dessous.</p>
          ) : (
            <div className="validation-actions">
              <select value={typeAlea} onChange={(e) => setTypeAlea(e.target.value)}>
                {TYPES_ALEA.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <input
                type="text"
                placeholder="Description de l'aléa"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
              <button onClick={handleLeverAlerte} disabled={enCours || !description}>
                Lever une alerte pour cette instance
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
