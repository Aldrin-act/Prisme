import type { SecteurActivite } from "@/integrations/prisme";

// Ressources typiques par secteur, à titre de suggestion cliquable (jamais un
// remplissage automatique aveugle) sur l'onglet Saisie T-R-C-O de
// ingestion-dialog.tsx. Valeurs reprises telles quelles des jeux de données
// de démo réels (scripts/generer_donnees_brutes.py) — pas des noms inventés.
export const RESSOURCES_SUGGEREES_PAR_SECTEUR: Record<
  SecteurActivite,
  { id: string; competences?: string[] }[]
> = {
  atelier_mecanique: [
    { id: "DECOUPEUSE_LASER" },
    { id: "PERCEUSE_CNC" },
    { id: "PRESSE_PLIAGE" },
    { id: "POSTE_SOUDURE_1" },
    { id: "POSTE_SOUDURE_2" },
    { id: "CABINE_PEINTURE" },
    { id: "POSTE_ASSEMBLAGE" },
    { id: "POSTE_CONTROLE" },
  ],
  assemblage_electronique: [
    { id: "STATION_PREP" },
    { id: "MACHINE_PICK_PLACE_1" },
    { id: "MACHINE_PICK_PLACE_2" },
    { id: "FOUR_REFUSION" },
    { id: "AOI_AUTOMATIQUE" },
    { id: "POSTE_SOUDURE_MANUEL" },
    { id: "BANC_TEST" },
    { id: "ROBOT_COATING" },
    { id: "POSTE_CONTROLE_VISUEL" },
  ],
  production_agroalimentaire: [
    { id: "QUAI_RECEPTION" },
    { id: "TUNNEL_LAVAGE" },
    { id: "LIGNE_EPLUCHAGE" },
    { id: "ROBOT_DECOUPE" },
    { id: "AUTOCLAVE_1" },
    { id: "TUNNEL_REFROIDISSEMENT" },
    { id: "LIGNE_CONDITIONNEMENT" },
    { id: "ETIQUETEUSE_AUTO" },
    { id: "ROBOT_PALETTISEUR" },
  ],
  maintenance_industrielle: [
    { id: "EQUIPE_DIAG" },
    { id: "SERVICE_ACHATS" },
    { id: "EQUIPE_MECA" },
    { id: "ATELIER_REPARATION" },
    { id: "EQUIPE_TEST" },
  ],
  imprimerie: [
    { id: "STATION_PAO" },
    { id: "PRESSE_OFFSET_1" },
    { id: "PRESSE_OFFSET_2" },
    { id: "TUNNEL_SECHAGE" },
    { id: "MACHINE_VERNIS" },
    { id: "PLIEUSE_COLLEUSE" },
    { id: "POSTE_FINITION" },
  ],
  // Seul secteur du jeu de démo à porter de vraies compétences (les 5 autres
  // n'en ont pas besoin pour rester représentatifs d'un ERP legacy pauvre).
  centre_appels: [
    { id: "POSTE_TELEPHONIQUE_N1", competences: ["telephonique_n1"] },
    { id: "POSTE_TELEPHONIQUE_N2", competences: ["telephonique_n2"] },
    { id: "SYSTEME_CRM", competences: ["systeme_crm"] },
    { id: "POSTE_SUPPORT_TECHNIQUE", competences: ["support_technique"] },
  ],
};
