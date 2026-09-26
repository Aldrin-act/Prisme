import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { z } from "zod";
import { ArrowLeft, Loader2, Eye, EyeOff } from "lucide-react";
import { PrismeLogo } from "@/components/prisme-logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/integrations/prisme/auth";
import { PrismeAPIError } from "@/integrations/prisme/client";
import { useClients } from "@/integrations/prisme";
import { toast } from "sonner";

const searchSchema = z.object({
  mode: z.enum(["signin", "signup"]).optional(),
});

export const Route = createFileRoute("/auth")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Connexion — PRISME" },
      {
        name: "description",
        content: "Accédez à la plateforme de planification industrielle PRISME.",
      },
      { property: "og:title", content: "Connexion — PRISME" },
      {
        property: "og:description",
        content: "Accédez à la plateforme de planification industrielle PRISME.",
      },
    ],
  }),
  validateSearch: searchSchema,
  component: AuthPage,
});

function AuthPage() {
  const { mode } = Route.useSearch();
  const navigate = useNavigate();
  const { estAuthentifie } = useAuth();

  useEffect(() => {
    if (estAuthentifie) navigate({ to: "/app", replace: true });
  }, [estAuthentifie, navigate]);

  return (
    <div
      className="relative flex min-h-screen items-center justify-center px-4 py-16"
      style={{ backgroundImage: "var(--gradient-hero)" }}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-30"
        style={{
          backgroundImage:
            "linear-gradient(oklch(1 0 0 / 0.06) 1px, transparent 1px), linear-gradient(90deg, oklch(1 0 0 / 0.06) 1px, transparent 1px)",
          backgroundSize: "56px 56px",
          maskImage: "radial-gradient(ellipse 60% 60% at 50% 40%, black, transparent 80%)",
        }}
      />
      <div className="relative w-full max-w-md">
        <Link
          to="/"
          className="mb-6 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Retour
        </Link>
        <div className="glass rounded-3xl p-8">
          <div className="mb-6 flex items-center gap-2">
            <PrismeLogo className="h-9 w-9" />
            <span className="text-lg font-bold">PRISME</span>
          </div>
          <h1 className="text-2xl font-bold">Bienvenue</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Connectez-vous ou créez votre compte pour accéder à la plateforme.
          </p>

          <Tabs defaultValue={mode === "signup" ? "signup" : "signin"} className="mt-6">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="signin">Se connecter</TabsTrigger>
              <TabsTrigger value="signup">Créer un compte</TabsTrigger>
            </TabsList>
            <TabsContent value="signin">
              <SignInForm />
            </TabsContent>
            <TabsContent value="signup">
              <SignUpForm />
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}

const emailSchema = z.string().trim().email("Email invalide").max(255);
const passwordSchema = z.string().min(8, "8 caractères minimum").max(72);

function messageErreurAuth(error: unknown): string {
  if (error instanceof PrismeAPIError) {
    switch (error.detail) {
      case "INVALID_CREDENTIALS":
        return "Email ou mot de passe incorrect";
      case "USER_EXISTS":
        return "Un compte existe déjà avec cet email";
      case "UNAUTHORIZED":
        return "Accès non autorisé";
      case "TOKEN_EXPIRED":
        return "Session expirée, merci de vous reconnecter";
      default:
        return error.message;
    }
  }
  return "Erreur de connexion";
}

function SignInForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const emailOk = emailSchema.safeParse(email);
    const pwOk = passwordSchema.safeParse(password);
    if (!emailOk.success) return toast.error(emailOk.error.issues[0].message);
    if (!pwOk.success) return toast.error(pwOk.error.issues[0].message);
    setLoading(true);
    try {
      await login({ email, password });
      toast.success("Content de vous revoir");
      navigate({ to: "/app" });
    } catch (error) {
      toast.error(messageErreurAuth(error));
    } finally {
      setLoading(false);
    }
  }
  return (
    <form onSubmit={onSubmit} className="mt-4 space-y-4">
      <Field label="Email">
        <Input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="vous@entreprise.com"
          required
        />
      </Field>
      <PasswordField
        label="Mot de passe"
        value={password}
        onChange={setPassword}
        placeholder="••••••••"
        required
      />
      <Button
        type="submit"
        disabled={loading}
        className="w-full bg-gradient-to-r from-primary to-accent"
      >
        {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        Se connecter
      </Button>
    </form>
  );
}

function SignUpForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [prenom, setPrenom] = useState("");
  const [nom, setNom] = useState("");
  const [clientId, setClientId] = useState("");
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();
  const { data: clients, isLoading: clientsEnChargement } = useClients();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const emailOk = emailSchema.safeParse(email);
    const pwOk = passwordSchema.safeParse(password);
    if (!emailOk.success) return toast.error(emailOk.error.issues[0].message);
    if (!pwOk.success) return toast.error(pwOk.error.issues[0].message);
    if (!prenom.trim() || !nom.trim())
      return toast.error("Merci de renseigner votre prénom et votre nom");
    if (!clientId) return toast.error("Merci de sélectionner votre client");
    setLoading(true);
    try {
      await register({ email, password, prenom, nom, client_id: clientId });
      toast.success("Compte créé");
      navigate({ to: "/app" });
    } catch (error) {
      toast.error(messageErreurAuth(error));
    } finally {
      setLoading(false);
    }
  }
  return (
    <form onSubmit={onSubmit} className="mt-4 space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Prénom">
          <Input
            value={prenom}
            onChange={(e) => setPrenom(e.target.value)}
            placeholder="Jeanne"
            required
          />
        </Field>
        <Field label="Nom">
          <Input
            value={nom}
            onChange={(e) => setNom(e.target.value)}
            placeholder="Dupont"
            required
          />
        </Field>
      </div>
      <Field label="Email">
        <Input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="vous@entreprise.com"
          required
        />
      </Field>
      <Field label="Client">
        <Select value={clientId} onValueChange={setClientId}>
          <SelectTrigger>
            <SelectValue
              placeholder={clientsEnChargement ? "Chargement..." : "Sélectionnez votre client"}
            />
          </SelectTrigger>
          <SelectContent>
            {clients?.map((c) => (
              <SelectItem key={c.client_id} value={c.client_id}>
                {c.nom || c.client_id}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <PasswordField
        label="Mot de passe"
        value={password}
        onChange={setPassword}
        placeholder="8 caractères minimum"
        required
      />
      <Button
        type="submit"
        disabled={loading}
        className="w-full bg-gradient-to-r from-primary to-accent"
      >
        {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        Créer un compte
      </Button>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs uppercase tracking-wider text-muted-foreground">{label}</Label>
      {children}
    </div>
  );
}

function PasswordField({
  label,
  value,
  onChange,
  placeholder,
  required,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <Field label={label}>
      <div className="relative">
        <Input
          type={visible ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          required={required}
          className="pr-10"
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          aria-label={visible ? "Masquer le mot de passe" : "Afficher le mot de passe"}
        >
          {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
    </Field>
  );
}
