import {
  createFileRoute,
  Outlet,
  redirect,
  Link,
  useNavigate,
  useRouterState,
} from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  LayoutDashboard,
  Database,
  FolderKanban,
  Cpu,
  FileCode2,
  Calendar,
  ShieldAlert,
  Bell,
  KeyRound,
  Settings,
  LogOut,
  Search,
  Building2,
  Loader2,
  ClipboardList,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { authService, useAuth } from "@/integrations/prisme/auth";
import { useJobsGeneration } from "@/integrations/prisme";
import { toast } from "sonner";
import { PrismeLogo } from "@/components/prisme-logo";

export const Route = createFileRoute("/_authenticated")({
  ssr: false,
  beforeLoad: async () => {
    const session = authService.getSession();
    if (!session) throw redirect({ to: "/auth" });
    return { utilisateur: session.utilisateur };
  },
  component: AppShell,
});

const NAV = [
  { to: "/app", icon: LayoutDashboard, label: "Tableau de bord" },
  { to: "/donnees", icon: Database, label: "Données" },
  { to: "/instances", icon: FolderKanban, label: "Instances" },
  { to: "/commandes", icon: ClipboardList, label: "Commandes" },
  { to: "/solver-generator", icon: Cpu, label: "Générateur de solveurs" },
  { to: "/solvers", icon: FileCode2, label: "Solveurs générés" },
  { to: "/schedules", icon: Calendar, label: "Plannings" },
  { to: "/supervision", icon: ShieldAlert, label: "Supervision" },
  { to: "/clients", icon: Building2, label: "Clients", rolesAutorises: ["admin"] },
  { to: "/api-keys", icon: KeyRound, label: "Clés API" },
  { to: "/settings", icon: Settings, label: "Paramètres" },
] as const;

function AppShell() {
  const { utilisateur } = Route.useRouteContext();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  async function signOut() {
    await qc.cancelQueries();
    qc.clear();
    await logout();
    toast.success("Déconnecté");
    navigate({ to: "/auth", replace: true });
  }

  const navVisible = NAV.filter(
    (n) =>
      !("rolesAutorises" in n) ||
      (n.rolesAutorises as readonly string[]).includes(utilisateur.role),
  );
  const current = NAV.find((n) => n.to === pathname);

  // Icône de progression sur l'onglet "Générateur de solveurs", visible
  // depuis n'importe quelle page — même principe qu'un onglet de navigateur
  // qui tourne tant qu'une page charge.
  const { data: jobsGeneration } = useJobsGeneration();
  const generationEnCours = jobsGeneration?.some((j) => !j.termine) ?? false;

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-64 shrink-0 self-start border-r border-border/50 p-4 md:sticky md:top-0 md:flex md:h-screen md:flex-col">
        <Link to="/" className="flex items-center gap-2 px-2 py-2">
          <PrismeLogo className="h-8 w-8" />
          <span className="font-bold tracking-tight">PRISME</span>
        </Link>
        <nav className="mt-6 flex-1 space-y-1 overflow-y-auto">
          {navVisible.map((n) => {
            const active = pathname === n.to;
            return (
              <Link
                key={n.to}
                to={n.to}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                  active
                    ? "bg-gradient-to-r from-primary/20 to-accent/20 text-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                <n.icon className="h-4 w-4" />
                {n.label}
                {n.to === "/solver-generator" && generationEnCours && (
                  <Loader2 className="ml-auto h-3.5 w-3.5 shrink-0 animate-spin text-primary" />
                )}
              </Link>
            );
          })}
        </nav>
        <div className="mt-4 border-t border-border/50 pt-4">
          <div className="truncate px-2 text-xs text-muted-foreground">
            {utilisateur.prenom} {utilisateur.nom}
          </div>
          <Button variant="ghost" size="sm" className="mt-2 w-full justify-start" onClick={signOut}>
            <LogOut className="mr-2 h-4 w-4" /> Se déconnecter
          </Button>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <header className="glass sticky top-0 z-10 flex items-center justify-between border-b border-border/50 px-6 py-4">
          <div>
            <div className="text-xs uppercase tracking-widest text-muted-foreground">
              Espace de travail
            </div>
            <h1 className="text-lg font-semibold">{current?.label ?? "PRISME"}</h1>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative hidden md:block">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input placeholder="Rechercher…" className="w-72 pl-9" />
            </div>
            <Button variant="outline" size="icon" aria-label="Notifications">
              <Bell className="h-4 w-4" />
            </Button>
          </div>
        </header>
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
