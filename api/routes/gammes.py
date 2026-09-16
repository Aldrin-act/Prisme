"""Gammes opératoires réutilisables : une `GammeProduit` décrit une fois, par produit, la séquence
d'étapes (compétences requises, ordre) qui s'explose en tâches concrètes à chaque nouvelle
commande qui la référence — une commande peut en référencer plusieurs (plusieurs produits, voir
`adapters/gamme_derivation.py`, route `POST /ingestion/{instance_id}/commandes`). Volontairement
minimal, même statut que `SourceDonnees` (`api/routes/sources.py`) : ne porte aucun historique
d'exécution, aucune instance "courante"."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.autorisation import client_id_pour_filtre, verifier_acces_client
from api.etat import EtapeGamme, EtatAPI, GammeProduit, obtenir_etat
from api.routes.auth import obtenir_utilisateur_courant

router = APIRouter(prefix="/gammes", tags=["gammes"])


class EtapeGammeRequete(BaseModel):
    id: str
    competences: list[str] = Field(min_length=1)
    predecesseurs: list[str] = Field(default_factory=list)
    duree_nominale: int | None = Field(default=None, gt=0)


class RequeteGamme(BaseModel):
    produit: str
    nom: str | None = None
    etapes: list[EtapeGammeRequete] = Field(min_length=1)
    client_id: str | None = None  # admin uniquement : cible un client autre que le sien


def _client_id_effectif(requete_client_id: str | None, utilisateur: dict) -> str:
    """Même contrat que `sources.py::_client_id_effectif` (dupliqué plutôt que centralisé,
    convention déjà établie — voir aussi `supervision.py`, qui a son propre contrat distinct)."""
    if utilisateur.get("role") == "admin" and requete_client_id:
        return requete_client_id
    client_id = utilisateur.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="compte sans client_id associé")
    return client_id


def _etapes_domaine(etapes: list[EtapeGammeRequete]) -> tuple[EtapeGamme, ...]:
    return tuple(
        EtapeGamme(
            id=e.id,
            competences=tuple(e.competences),
            predecesseurs=tuple(e.predecesseurs),
            duree_nominale=e.duree_nominale,
        )
        for e in etapes
    )


def _gamme_vers_dict(gamme: GammeProduit) -> dict[str, object]:
    return {
        "gamme_id": gamme.id,
        "client_id": gamme.client_id,
        "produit": gamme.produit,
        "nom": gamme.nom,
        "etapes": [
            {
                "id": e.id,
                "competences": list(e.competences),
                "predecesseurs": list(e.predecesseurs),
                "duree_nominale": e.duree_nominale,
            }
            for e in gamme.etapes
        ],
    }


@router.post("")
def creer_gamme(
    requete: RequeteGamme,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, str]:
    client_id = _client_id_effectif(requete.client_id, utilisateur)
    gamme_id = etat.enregistrer_gamme(client_id, requete.produit, _etapes_domaine(requete.etapes), requete.nom)
    return {"gamme_id": gamme_id}


@router.get("")
def lister_gammes(
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> list[dict[str, object]]:
    return [_gamme_vers_dict(g) for g in etat.lister_gammes(client_id=client_id_pour_filtre(utilisateur))]


@router.get("/{gamme_id}")
def obtenir_gamme(
    gamme_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    try:
        gamme = etat.recuperer_gamme(gamme_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="gamme inconnue") from None

    verifier_acces_client(utilisateur, gamme.client_id)
    return _gamme_vers_dict(gamme)


@router.put("/{gamme_id}")
def modifier_gamme(
    gamme_id: str,
    requete: RequeteGamme,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    try:
        gamme_existante = etat.recuperer_gamme(gamme_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="gamme inconnue") from None

    verifier_acces_client(utilisateur, gamme_existante.client_id)
    gamme = etat.modifier_gamme(gamme_id, requete.produit, _etapes_domaine(requete.etapes), requete.nom)
    return _gamme_vers_dict(gamme)


@router.delete("/{gamme_id}", status_code=204)
def supprimer_gamme(
    gamme_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> None:
    try:
        gamme = etat.recuperer_gamme(gamme_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="gamme inconnue") from None

    verifier_acces_client(utilisateur, gamme.client_id)
    etat.supprimer_gamme(gamme_id)
