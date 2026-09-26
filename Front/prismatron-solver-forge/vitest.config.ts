// Config de test séparée de `vite.config.ts` : la config Lovable y ajoute TanStack Start, Nitro et
// les plugins de dev, inutiles pour tester des fonctions pures. Seul l'alias `@/` est repris.
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: { tsconfigPaths: true },
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
  },
});
