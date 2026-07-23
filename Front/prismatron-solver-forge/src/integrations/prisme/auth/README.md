# Authentification PRISME

Système d'authentification complet pour les maintenants et opérateurs PRISME.

---

## 🔐 Rôles & Permissions

### Rôles disponibles

1. **Opérateur** : Utilisation basique
   - Lire instances
   - Créer instances
   - Exécuter solveurs
   - Valider plannings

2. **Maintenant** : Maintenance et diagnostic
   - Toutes les permissions Opérateur +
   - Diagnostiquer
   - Voir audit (code source)

3. **Admin** : Administration complète
   - Toutes les permissions Maintenant +
   - Gérer utilisateurs
   - Configurer système

### Matrice des permissions

| Permission | Opérateur | Maintenant | Admin |
|---|---|---|---|
| lire_instances | ✅ | ✅ | ✅ |
| creer_instances | ✅ | ✅ | ✅ |
| executer_solveurs | ✅ | ✅ | ✅ |
| valider_plannings | ✅ | ✅ | ✅ |
| diagnostiquer | ❌ | ✅ | ✅ |
| voir_audit | ❌ | ✅ | ✅ |
| gerer_utilisateurs | ❌ | ❌ | ✅ |
| configurer_systeme | ❌ | ❌ | ✅ |

---

## 🚀 Installation

### 1. Envelopper votre app avec le Provider

```typescript
// src/App.tsx ou src/router.tsx
import { AuthProvider } from '@/integrations/prisme/auth';

function App() {
  return (
    <AuthProvider>
      {/* Votre application */}
    </AuthProvider>
  );
}
```

### 2. Utiliser dans vos composants

```typescript
import { useAuth, ProtectedRoute, UserMenu } from '@/integrations/prisme/auth';

function Dashboard() {
  const { utilisateur, logout } = useAuth();

  return (
    <div>
      <h1>Bienvenue {utilisateur?.prenom}</h1>
      <UserMenu />
    </div>
  );
}
```

---

## 📖 Utilisation

### Connexion

```typescript
import { useAuth } from '@/integrations/prisme/auth';

function LoginPage() {
  const { login } = useAuth();

  const handleLogin = async () => {
    try {
      await login({
        email: 'maintenant@example.com',
        password: 'password123',
      });
      // Redirection automatique ou manuelle
      window.location.href = '/dashboard';
    } catch (error) {
      console.error('Échec connexion:', error);
    }
  };

  return (
    <button onClick={handleLogin}>
      Se connecter
    </button>
  );
}
```

### Ou utiliser le composant prêt à l'emploi (recommandé)

```typescript
import { LoginForm } from '@/integrations/prisme/auth';

function LoginPage() {
  return <LoginForm />;
}
```

**Fonctionnalités incluses** :
- Formulaire de connexion complet avec validation
- Affichage des comptes de test avec boutons "Utiliser" pour remplir instantanément le formulaire
- Gestion d'erreurs avec messages d'erreur clairs
- États de chargement pendant la connexion
- Design responsive et accessible

**Comptes de test disponibles** :
- **Maintenant** : `maintenant@example.com` / `password_123`
- **Admin** : `admin@example.com` / `password_456`

---

### Protection de routes

```typescript
import { ProtectedRoute } from '@/integrations/prisme/auth';

// Route accessible uniquement aux maintenants
function DiagnosticPage() {
  return (
    <ProtectedRoute requiredRole="maintenant">
      <div>Diagnostic avancé...</div>
    </ProtectedRoute>
  );
}

// Route accessible aux maintenants ET admins
function AuditPage() {
  return (
    <ProtectedRoute requiredRole={['maintenant', 'admin']}>
      <div>Code source audit...</div>
    </ProtectedRoute>
  );
}

// Route avec permission spécifique
function UserManagementPage() {
  return (
    <ProtectedRoute requiredPermission="gerer_utilisateurs">
      <div>Gestion utilisateurs...</div>
    </ProtectedRoute>
  );
}
```

---

### Vérification conditionnelle

```typescript
import { useAuth } from '@/integrations/prisme/auth';

function ActionsPanel() {
  const { aPermission, aRole } = useAuth();

  return (
    <div>
      {aPermission('diagnostiquer') && (
        <button>Lancer Diagnostic</button>
      )}

      {aRole('admin') && (
        <button>Gérer Utilisateurs</button>
      )}

      {aRole('maintenant', 'admin') && (
        <button>Voir Audit</button>
      )}
    </div>
  );
}
```

---

### Menu utilisateur

```typescript
import { UserMenu } from '@/integrations/prisme/auth';

function Header() {
  return (
    <header>
      <h1>PRISME</h1>
      <UserMenu />
    </header>
  );
}
```

---

### Déconnexion

```typescript
import { useAuth } from '@/integrations/prisme/auth';

function LogoutButton() {
  const { logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    window.location.href = '/login';
  };

  return <button onClick={handleLogout}>Déconnexion</button>;
}
```

---

## 🔑 Gestion du token

Le token JWT est automatiquement :
- Stocké dans localStorage
- Ajouté aux headers des requêtes API
- Rafraîchi 5 minutes avant expiration
- Supprimé à la déconnexion

### Token dans les requêtes API

```typescript
// Le client PRISME utilise automatiquement le token
import { prismeClient } from '@/integrations/prisme';

// Cette requête inclura automatiquement: Authorization: Bearer <token>
const instances = await prismeClient.listerInstances();
```

---

## 🛡️ Backend (Python/FastAPI)

### Routes requises

Créez ces routes dans votre API FastAPI :

```python
# api/routes/auth.py
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta
import jwt

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
def login(credentials: CredentialsLogin):
    # Vérifier email/password
    # Générer JWT token
    # Retourner session
    pass

@router.post("/register")
def register(credentials: CredentialsRegister):
    # Créer utilisateur
    # Générer JWT token
    # Retourner session
    pass

@router.post("/logout")
def logout(token: str = Depends(get_token)):
    # Invalider token (blacklist)
    pass

@router.post("/refresh")
def refresh_token(token: str = Depends(get_token)):
    # Vérifier token actuel
    # Générer nouveau token
    # Retourner nouvelle session
    pass

@router.get("/verify")
def verify_token(token: str = Depends(get_token)):
    # Vérifier validité token
    return {"valid": True}
```

### Middleware d'authentification

```python
# api/dependencies.py
from fastapi import Header, HTTPException
import jwt

def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Token manquant")

    token = authorization.replace("Bearer ", "")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload  # { "user_id": "...", "role": "maintenant", ... }
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, {"code": "TOKEN_EXPIRED", "message": "Token expiré"})
    except jwt.InvalidTokenError:
        raise HTTPException(401, {"code": "UNAUTHORIZED", "message": "Token invalide"})
```

### Protection des routes

```python
from fastapi import Depends

@router.get("/supervision/instances")
def lister_instances(user = Depends(get_current_user)):
    # Vérifie que l'utilisateur est authentifié
    # user = { "user_id": "...", "role": "maintenant", ... }
    pass

@router.post("/diagnostics/{execution_id}")
def diagnostiquer(
    execution_id: str,
    user = Depends(require_permission("diagnostiquer"))
):
    # Seulement maintenants et admins
    pass
```

---

## 🔧 Configuration

### Variables d'environnement (Backend)

```env
# .env backend
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440  # 24 heures
```

### Schéma base de données

```sql
CREATE TABLE utilisateurs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('operateur', 'maintenant', 'admin')),
    client_id VARCHAR(50),  -- Pour opérateurs liés à un client
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    dernier_acces TIMESTAMP,
    actif BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_utilisateurs_email ON utilisateurs(email);
CREATE INDEX idx_utilisateurs_role ON utilisateurs(role);
```

---

## 📊 Exemples avancés

### Wrapper de route avec permissions

```typescript
// src/components/PermissionGate.tsx
import { ReactNode } from 'react';
import { useAuth } from '@/integrations/prisme/auth';
import type { PermissionsRole } from '@/integrations/prisme/auth';

interface PermissionGateProps {
  permission: keyof PermissionsRole;
  children: ReactNode;
  fallback?: ReactNode;
}

export function PermissionGate({ permission, children, fallback }: PermissionGateProps) {
  const { aPermission } = useAuth();

  if (!aPermission(permission)) {
    return fallback || null;
  }

  return <>{children}</>;
}

// Utilisation
<PermissionGate permission="diagnostiquer">
  <DiagnosticButton />
</PermissionGate>
```

### Hook personnalisé pour rôle

```typescript
export function useRequireRole(...roles: RoleUtilisateur[]) {
  const { aRole, estAuthentifie } = useAuth();

  if (!estAuthentifie || !aRole(...roles)) {
    throw new Error('Accès refusé');
  }
}

// Dans un composant
function AdminPanel() {
  useRequireRole('admin');

  return <div>Admin only</div>;
}
```

---

## 🐛 Dépannage

### Token expiré

Le token est automatiquement rafraîchi 5 min avant expiration. Si l'utilisateur est inactif > 24h, il sera déconnecté.

### Permissions non mises à jour

Après changement de rôle côté backend, l'utilisateur doit se déconnecter/reconnecter pour rafraîchir ses permissions.

### CORS

Assurez-vous que votre backend autorise les en-têtes :
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

**Version** : 1.0.0
**Dernière mise à jour** : 2026-07-22
