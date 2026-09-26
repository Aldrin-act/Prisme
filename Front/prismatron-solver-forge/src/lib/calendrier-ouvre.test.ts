import { describe, expect, it } from "vitest";

import { estInstantOuvre, finCalendaire, segmentsTravailles } from "@/lib/calendrier-ouvre";

// Dates construites en heure locale, comme le fait l'application (`dateDepuisAncrage`) : les
// résultats ne dépendent pas du fuseau de la machine. Semaine choisie loin de tout changement d'heure.
// Lundi 28 septembre 2026, 19h.
const LUNDI_19H = new Date(2026, 8, 28, 19, 0, 0);
// Vendredi 2 octobre 2026, 20h.
const VENDREDI_20H = new Date(2026, 9, 2, 20, 0, 0);

describe("estInstantOuvre", () => {
  it("ouvré en semaine entre 8h et 22h, fermé la nuit (mode heures)", () => {
    expect(estInstantOuvre(0, LUNDI_19H, "heures")).toBe(true); // lundi 19h
    expect(estInstantOuvre(2, LUNDI_19H, "heures")).toBe(true); // lundi 21h
    expect(estInstantOuvre(3, LUNDI_19H, "heures")).toBe(false); // lundi 22h
    expect(estInstantOuvre(12, LUNDI_19H, "heures")).toBe(false); // mardi 7h
    expect(estInstantOuvre(13, LUNDI_19H, "heures")).toBe(true); // mardi 8h
  });

  it("le week-end est fermé, quel que soit le mode", () => {
    expect(estInstantOuvre(5, new Date(2026, 8, 28), "jours")).toBe(false); // samedi
    expect(estInstantOuvre(4, new Date(2026, 8, 28), "jours")).toBe(true); // vendredi
  });
});

describe("segmentsTravailles / finCalendaire", () => {
  it("exemple de la spec : démarrée à 19h avec 5 h, finit à 10h le lendemain", () => {
    // 19h-22h (3 h) puis 8h-10h (2 h) : la nuit est traversée sans être comptée.
    expect(segmentsTravailles(0, 5, LUNDI_19H, "heures")).toEqual([
      { debut: 0, fin: 3 },
      { debut: 13, fin: 15 },
    ]);
    expect(finCalendaire(0, 5, LUNDI_19H, "heures")).toBe(15);
  });

  it("traverse le week-end : vendredi 20h + 4 h finit lundi 10h", () => {
    // Vendredi 20h-22h (2 h), samedi et dimanche fermés, lundi 8h-10h (2 h).
    const lundi10h = (new Date(2026, 9, 5, 10).getTime() - VENDREDI_20H.getTime()) / 3_600_000;
    expect(finCalendaire(0, 4, VENDREDI_20H, "heures")).toBe(lundi10h);
  });

  it("une opération qui tient dans la journée reste d'un seul tenant", () => {
    expect(segmentsTravailles(0, 2, LUNDI_19H, "heures")).toEqual([{ debut: 0, fin: 2 }]);
  });

  it("en mode jours, aucune pause : fin = début + durée", () => {
    expect(segmentsTravailles(3, 4, LUNDI_19H, "jours")).toEqual([{ debut: 3, fin: 7 }]);
    expect(finCalendaire(3, 4, LUNDI_19H, "jours")).toBe(7);
  });

  it("une durée nulle ne boucle pas", () => {
    expect(finCalendaire(0, 0, LUNDI_19H, "heures")).toBe(0);
  });
});
