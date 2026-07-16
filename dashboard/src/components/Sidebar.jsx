const ONGLETS = [
  { id: "ingestion", libelle: "Ingestion", icone: "＋" },
  { id: "planning", libelle: "Planning", icone: "▤" },
  { id: "diagnostic", libelle: "Diagnostic", icone: "◎" },
];

// Barre latérale : pure navigation par onglets (§2.3, PH10-T1). Chaque
// onglet correspond à une vue distincte du contenu principal ; la sidebar
// ne porte plus aucune logique métier — ça vit dans les panneaux du
// contenu principal.
export default function Sidebar({ onglet, onChangerOnglet }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-entete">
        <h1>PRISME</h1>
        <p className="sous-titre">Le système propose, l'humain décide.</p>
      </div>

      <nav className="sidebar-nav">
        {ONGLETS.map((o) => (
          <button
            key={o.id}
            className={`nav-item ${onglet === o.id ? "actif" : ""}`}
            onClick={() => onChangerOnglet(o.id)}
          >
            <span className="nav-item-icone" aria-hidden="true">{o.icone}</span>
            {o.libelle}
          </button>
        ))}
      </nav>
    </aside>
  );
}
