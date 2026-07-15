// Visualisation Gantt faite main (barres HTML/CSS), pas de bibliothèque de
// graphique — suffisant pour une démo/mémoire, cohérent avec l'esprit
// "noyau minimal" du reste du projet. `Planning` n'a pas de champ durée par
// design (dsl/schema/planning.py) : les durées viennent du champ `durees`
// ajouté par l'API (clé "{tache}|{ressource}"), pas de `operation` lui-même.
export default function GanttChart({ planning }) {
  if (!planning) return null;

  const { operations, durees } = planning;
  const finDe = (op) => op.debut + (durees[`${op.tache}|${op.ressource}`] ?? 0);
  const echelle = Math.max(1, ...operations.map(finDe));

  const ressources = [...new Set(operations.map((op) => op.ressource))].sort();

  return (
    <div className="gantt">
      {ressources.map((ressource) => (
        <div className="gantt-ligne" key={ressource}>
          <span className="gantt-ressource">{ressource}</span>
          <div className="gantt-piste">
            {operations
              .filter((op) => op.ressource === ressource)
              .map((op) => {
                const duree = durees[`${op.tache}|${op.ressource}`] ?? 0;
                return (
                  <div
                    key={op.tache}
                    className="gantt-barre"
                    title={`${op.tache} : ${op.debut} → ${op.debut + duree}`}
                    style={{
                      left: `${(op.debut / echelle) * 100}%`,
                      width: `${(duree / echelle) * 100}%`,
                    }}
                  >
                    {op.tache}
                  </div>
                );
              })}
          </div>
        </div>
      ))}
    </div>
  );
}
