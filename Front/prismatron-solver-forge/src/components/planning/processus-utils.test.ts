import { describe, expect, it } from "vitest";

import type { EtapeProcessus } from "@/integrations/prisme";
import {
  competencesDe,
  enchainementsDistincts,
  estProcessusSimple,
  etapesDepuisTaches,
  idDepuisNom,
  ordreChaine,
} from "@/components/planning/processus-utils";

function etape(id: string, predecesseurs: string[] = [], competences = ["c"]): EtapeProcessus {
  return { id, nom: id, competences, predecesseurs, duree_par_piece: 1 };
}

describe("competencesDe", () => {
  it("découpe sur les virgules et ignore les vides", () => {
    expect(competencesDe(" soudure, peinture ,, ")).toEqual(["soudure", "peinture"]);
  });
});

describe("idDepuisNom", () => {
  it("retire les accents et remplace le reste par des _", () => {
    expect(idDepuisNom("Contrôle final")).toBe("CONTROLE_FINAL");
    expect(idDepuisNom("  Découpe / laser  ")).toBe("DECOUPE_LASER");
  });

  it("reste dans la limite de 40 caractères imposée côté serveur", () => {
    expect(idDepuisNom("x".repeat(60))).toHaveLength(40);
  });
});

describe("ordreChaine", () => {
  it("remet une suite simple dans l'ordre, même déclarée en désordre", () => {
    const etapes = [etape("C", ["B"]), etape("A"), etape("B", ["A"])];
    expect(ordreChaine(etapes)?.map((e) => e.id)).toEqual(["A", "B", "C"]);
    expect(estProcessusSimple(etapes)).toBe(true);
  });

  it("refuse une fusion (étape à deux prédécesseurs)", () => {
    expect(ordreChaine([etape("A"), etape("B"), etape("C", ["A", "B"])])).toBeNull();
  });

  it("refuse deux branches parallèles", () => {
    expect(ordreChaine([etape("A"), etape("B", ["A"]), etape("C", ["A"])])).toBeNull();
  });

  it("refuse une étape à plusieurs compétences", () => {
    expect(ordreChaine([etape("A", [], ["soudure", "peinture"])])).toBeNull();
  });
});

describe("etapesDepuisTaches", () => {
  it("replie les copies d'une même tâche et garde la durée la plus courte", () => {
    const etapes = etapesDepuisTaches({
      taches: [
        { id: "cmd1_decoupe", nom: "Découpe" },
        { id: "cmd2_decoupe", nom: "Découpe" },
        { id: "cmd1_peinture", nom: "Peinture" },
      ],
      contraintes: [
        { type: "competence_requise", tache: "cmd1_decoupe", competence: "laser" },
        { type: "compatibilite_ressource_tache", tache: "cmd1_decoupe", ressource: "R1", duree: 5 },
        { type: "compatibilite_ressource_tache", tache: "cmd2_decoupe", ressource: "R2", duree: 3 },
        { type: "precedence", avant: "cmd1_decoupe", apres: "cmd1_peinture" },
      ],
    } as Parameters<typeof etapesDepuisTaches>[0]);

    expect(etapes).toEqual([
      {
        id: "DECOUPE",
        nom: "Découpe",
        competences: ["laser"],
        predecesseurs: [],
        duree_par_piece: 3,
      },
      {
        id: "PEINTURE",
        nom: "Peinture",
        competences: [],
        predecesseurs: ["DECOUPE"],
        duree_par_piece: 0,
      },
    ]);
  });
});

describe("enchainementsDistincts", () => {
  it("sépare les étapes sans lien avec le reste du processus", () => {
    const groupes = enchainementsDistincts([etape("A"), etape("B", ["A"]), etape("X")]);
    expect(groupes.map((g) => g.map((e) => e.id))).toEqual([["A", "B"], ["X"]]);
  });
});
