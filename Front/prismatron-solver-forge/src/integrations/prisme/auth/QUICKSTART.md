# 🚀 Démarrage Rapide - Authentification PRISME

Guide de mise en place en 5 minutes.

---

## 📦 1. Installation Backend (API)

### Installer les dépendances

```bash
cd ../Prisme
uv sync  # Installe PyJWT et python-multipart automatiquement
```

### Comptes de test disponibles

2 comptes sont préconfigurés :

**Maintenant**
- Email : `maintenant@example.com`
- Password : `password_123`
- Rôle : Maintenant (toutes permissions sauf admin)

**Admin**
- Email : `admin@example.com`
- Password : `password_456`
- Rôle : Admin (toutes permissions)

### Démarrer l'API

```bash
uv run uvicorn api.app:app --reload
```

L'API est maintenant sur http://localhost:8000
Documentation : http://localhost:8000/docs

---

## ⚛️ 2. Installation Frontend

### Envelopper votre app

```typescript
// src/router.tsx ou src/main.tsx
import { AuthProvider } from '@/integrations/prisme/auth';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        {/* Votre app ici */}
        <Router />
      </AuthProvider>
    </QueryClientProvider>
  );
}
```

---

## 🔐 3. Page de connexion

### Option A : Composant prêt à l'emploi (avec comptes de test intégrés)

```typescript
// src/routes/login.tsx
import { LoginForm } from '@/integrations/prisme/auth';

export function LoginPage() {
  return <LoginForm />;
}
```

**Note** : Le formulaire affiche automatiquement les comptes de test avec des boutons "Utiliser" pour remplir instantanément le formulaire. Idéal pour le développement et les démos.

### Option B : Personnalisé

```typescript
import { useAuth } from '@/integrations/prisme/auth';
import { useState } from 'react';

export function CustomLoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login({ email, password });
      window.location.href = '/dashboard';
    } catch (error) {
      alert('Identifiants incorrects');
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Mot de passe"
      />
      <button type="submit">Connexion</button>
    </form>
  );
}
```

---

## 🛡️ 4. Protection des routes

```typescript
import { ProtectedRoute } from '@/integrations/prisme/auth';

// Page accessible seulement aux maintenants
export function DiagnosticPage() {
  return (
    <ProtectedRoute requiredRole="maintenant">
      <div>
        <h1>Diagnostic Avancé</h1>
        {/* Contenu réservé aux maintenants */}
      </div>
    </ProtectedRoute>
  );
}

// Page accessible aux maintenants ET admins
export function AuditPage() {
  return (
    <ProtectedRoute requiredRole={['maintenant', 'admin']}>
      <div>
        <h1>Audit Code Source</h1>
        {/* Contenu réservé */}
      </div>
    </ProtectedRoute>
  );
}
```

---

## 👤 5. Afficher l'utilisateur connecté

```typescript
import { UserMenu } from '@/integrations/prisme/auth';

export function Header() {
  return (
    <header className="flex justify-between items-center p-4">
      <h1>PRISME</h1>
      <UserMenu />
    </header>
  );
}
```

---

## ✅ 6. Test complet

### Tester la connexion

1. Démarrer l'API : `uv run uvicorn api.app:app --reload`
2. Démarrer le frontend : `bun run dev`
3. Accéder à http://localhost:5173/login
4. Se connecter avec :
   - **Email** : maintenant@example.com
   - **Password** : password_123
5. Vérifier que vous êtes redirigé vers le dashboard

### Tester les permissions

Créez une page protégée :

```typescript
// src/routes/diagnostic.tsx
import { ProtectedRoute } from '@/integrations/prisme/auth';

export function DiagnosticRoute() {
  return (
    <ProtectedRoute requiredRole="maintenant">
      <h1>Page Diagnostic</h1>
      <p>Visible seulement par les maintenants</p>
    </ProtectedRoute>
  );
}
```

Essayez d'accéder à `/diagnostic` :
- ✅ Avec le compte `maintenant@example.com` → **Accès autorisé**
- ❌ Avec un compte opérateur → **403 Accès refusé**

---

## 🔧 Configuration Production

### Backend

**Environnement** (`.env`) :

```env
# Clé secrète JWT (générer avec: openssl rand -hex 32)
JWT_SECRET_KEY=votre_cle_secrete_ultra_longue_et_aleatoire

# Durée de validité du token (en minutes)
JWT_EXPIRE_MINUTES=1440

# Base de données (en prod)
DATABASE_URL=postgresql://user:pass@localhost/prisme
```

**Sécurité** :

```python
# api/routes/auth.py
import os

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY doit être défini")
```

### Frontend

**Environnement** (`.env.local`) :

```env
VITE_PRISME_API_URL=http://localhost:8000
```

En production, pointer vers votre API déployée :

```env
VITE_PRISME_API_URL=https://api.prisme.votredomaine.com
```

---

## 🐛 Dépannage

### Erreur 401 sur toutes les requêtes

**Cause** : Token manquant ou invalide
**Solution** : Se déconnecter puis se reconnecter

### Pas d'en-tête Authorization dans les requêtes

**Cause** : Le service auth n'ajoute pas automatiquement le token
**Solution** : Vérifier que `authService.getToken()` retourne bien un token

### CORS errors

**Cause** : Frontend et backend sur ports différents
**Solution** : Vérifier le middleware CORS dans `api/app.py` :

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)
```

---

## 📚 Ressources

- **Documentation complète** : `./README.md`
- **API Documentation** : http://localhost:8000/docs
- **Exemples composants** : `./components/`

---

## ✨ Prochaines étapes

1. Remplacer la DB en mémoire par PostgreSQL
2. Implémenter le hashing bcrypt pour les mots de passe
3. Ajouter blacklist Redis pour tokens révoqués
4. Implémenter reset password par email
5. Ajouter 2FA (optionnel)

**Version** : 1.0.0
