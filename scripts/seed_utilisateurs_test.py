"""Script de seed pour créer les utilisateurs de test dans PostgreSQL.

Crée les comptes maintenant@example.com et admin@example.com avec mots de passe
bcrypt, pour les tests du frontend (remplace l'ancien UTILISATEURS_DB en mémoire).

Usage:
    python -m scripts.seed_utilisateurs_test
    # Ou si le backend FastAPI tourne déjà, simplement:
    # Les utilisateurs seront créés au premier login via /auth/register
"""

from __future__ import annotations

from api.auth_db import UtilisateursDB


def seed_utilisateurs_test() -> None:
    """Crée les utilisateurs de test dans PostgreSQL (schéma public)."""
    print("[SEED] Création des utilisateurs de test...")

    db = UtilisateursDB()

    # Liste des utilisateurs de test
    utilisateurs_test = [
        {
            "email": "maintenant@example.com",
            "mot_de_passe": "password_123",
            "nom": "Dupont",
            "prenom": "Jean",
            "role": "maintenant",
            "client_id": None,
        },
        {
            "email": "admin@example.com",
            "mot_de_passe": "password_456",
            "nom": "Admin",
            "prenom": "Super",
            "role": "admin",
            "client_id": None,
        },
        {
            "email": "operateur@example.com",
            "mot_de_passe": "password_789",
            "nom": "Martin",
            "prenom": "Sophie",
            "role": "operateur",
            "client_id": "demo",
        },
    ]

    for user_data in utilisateurs_test:
        # Vérifier si l'utilisateur existe déjà
        if db.email_existe(user_data["email"]):
            print(f"  [SKIP] {user_data['email']} existe deja")
            continue

        # Créer l'utilisateur
        user = db.creer_utilisateur(
            email=user_data["email"],
            mot_de_passe=user_data["mot_de_passe"],
            nom=user_data["nom"],
            prenom=user_data["prenom"],
            role=user_data["role"],  # type: ignore
            client_id=user_data["client_id"],
        )

        print(f"  [OK] {user.email} ({user.role}) cree avec ID {user.id}")

    print("\n[DONE] Seed termine ! Utilisateurs disponibles :")
    print("  - maintenant@example.com / password_123 (role: maintenant)")
    print("  - admin@example.com / password_456 (role: admin)")
    print("  - operateur@example.com / password_789 (role: operateur)")
    print("\nVous pouvez vous connecter via http://localhost:8082/auth")


if __name__ == "__main__":
    seed_utilisateurs_test()
