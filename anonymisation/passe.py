"""Passage des détecteurs sur les doléances, et écriture des offsets."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from anonymisation.detecteurs import (
    NON_PERSONNELS,
    Passage,
    detecter,
    formes,
    fusionner,
    signatures,
)
from database.models import Doleance, PiiSpan


def combiner(
    formes_et_signatures: list[Passage], entites: list[Passage]
) -> list[Passage]:
    """Fusionne les passages du modèle avec ceux des formes, sans qu'un lieu
    ou une organisation du modèle ne dé-caviarde une forme.

    `fusionner` fait gagner les genres non personnels sur un chevauchement,
    ce qui est juste entre formes (« Monsieur le Maire » est un rôle, pas un
    nom). Mais le modèle voit « rue des Lilas » comme un lieu là où la forme
    voit une adresse, et « accueil@ma-commune.fr » comme une organisation là où la
    forme voit un courriel : mesuré le 2026-09-11, la première passe avec NER
    perdait 214 adresses sur 255. Un lieu ou une organisation du modèle qui
    chevauche une forme est donc écarté ; ses personnes, elles, sont fusionnées
    normalement (un rôle public l'emporte, un nom se confond avec un nom).
    """
    gardes = [
        e
        for e in entites
        if e.genre not in NON_PERSONNELS
        or not any(e.debut < f.fin and f.debut < e.fin for f in formes_et_signatures)
    ]
    return fusionner(formes_et_signatures + gardes)


def lire_doleances(session: Session, run_segmentation: int) -> dict[int, str]:
    """``{doleance_id: texte}`` pour un découpage donné."""
    lignes = session.execute(
        select(Doleance.id, Doleance.text).where(
            Doleance.run_id == run_segmentation, Doleance.text.is_not(None)
        )
    ).all()
    return {identifiant: texte for identifiant, texte in lignes if texte}


def oublier_run(session: Session, run_id: int) -> None:
    """Efface les passages d'un run, pour le rejouer.

    Attention : les relectures humaines de ce run partent avec. C'est pour cela
    qu'un nouveau réglage crée un run de plus plutôt que d'écraser celui-ci.
    """
    session.execute(delete(PiiSpan).where(PiiSpan.run_id == run_id))
    session.flush()


def detecter_tout(
    session: Session,
    run_id: int,
    textes: dict[int, str],
    ner=None,
    *,
    commit_toutes_les: int = 100,
) -> dict[str, int]:
    """Passe les détecteurs sur chaque doléance et écrit les offsets.

    Args:
        session: session ouverte (le commit reste à l'appelant, sauf les
            commits intermédiaires : la NER prend des minutes, une
            interruption ne doit pas tout perdre).
        run_id: run d'anonymisation auquel rattacher les passages.
        textes: ``{doleance_id: texte}``.
        ner: un détecteur d'entités nommées (`ner.EntitesNommees`), ou rien.
            Ses passages sont fusionnés avec ceux des formes : les genres non
            personnels l'emportent sur un chevauchement.
        commit_toutes_les: nombre de doléances entre deux commits.

    Returns:
        ``{genre: nombre de passages}``.
    """
    comptes: dict[str, int] = {}
    for rang, (doleance_id, texte) in enumerate(textes.items(), start=1):
        passages = detecter(texte)
        if ner is not None:
            passages = combiner(
                fusionner(formes(texte) + signatures(texte)), ner.detecter(texte)
            )
        for passage in passages:
            session.add(
                PiiSpan(
                    run_id=run_id,
                    doleance_id=doleance_id,
                    start=passage.debut,
                    end=passage.fin,
                    kind=passage.genre,
                    detector=passage.detecteur,
                )
            )
            comptes[passage.genre] = comptes.get(passage.genre, 0) + 1
        if ner is not None and rang % commit_toutes_les == 0:
            session.commit()
    return comptes
