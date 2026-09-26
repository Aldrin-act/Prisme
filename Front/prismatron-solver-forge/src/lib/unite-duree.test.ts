import { describe, expect, it } from "vitest";

import { formatDuree, formatDureeCourte } from "@/lib/unite-duree";

describe("formatDuree", () => {
  it("accorde le pluriel en heures et en jours", () => {
    expect(formatDuree(1, "heures")).toBe("1 heure");
    expect(formatDuree(3, "heures")).toBe("3 heures");
    expect(formatDuree(1, "jours")).toBe("1 jour");
    expect(formatDuree(4, "jours")).toBe("4 jours");
  });

  it("une unité absente ou inconnue retombe sur les jours", () => {
    expect(formatDuree(2)).toBe("2 jours");
    expect(formatDuree(2, null)).toBe("2 jours");
    expect(formatDuree(2, "siecles")).toBe("2 jours");
  });

  it("garde toujours le nombre exact de jours quand l'unité affichée diffère", () => {
    expect(formatDuree(14, "semaines")).toBe("2 semaines (14 j.)");
    expect(formatDuree(25, "semaines")).toBe("3,6 semaines (25 j.)");
    expect(formatDuree(60, "mois")).toBe("2 mois (60 j.)");
  });
});

describe("formatDureeCourte", () => {
  it("abrège sans le rappel entre parenthèses", () => {
    expect(formatDureeCourte(5, "heures")).toBe("5 h.");
    expect(formatDureeCourte(5, "jours")).toBe("5 j.");
    expect(formatDureeCourte(25, "semaines")).toBe("3,6 sem.");
  });
});
