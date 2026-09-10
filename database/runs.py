"""Les runs : ce qui rend les couches interprétatives versionnées et plurielles.

Un run, c'est une production de couche : un découpage en doléances, une
livraison de l'équipe analyse. Il porte de quoi la rejouer et la juger — modèle,
version de prompt, paramètres, corpus, auteur, date.

Sept genres coexistent aujourd'hui : `SEGMENTATION`, `ANALYSE`, `DOUBLONS`,
`ANONYMISATION`, `EMBEDDINGS`, `TYPOLOGIE` et `TRANSCRIPTION`.
Dans chaque genre, un seul run est `active` : c'est celui que l'app et les exports servent
par défaut. Les autres restent en base, lisibles et comparables — c'est tout
l'intérêt : deux grilles de thèmes concurrentes doivent pouvoir coexister pour
que le choix de l'une soit visible et discutable.

**Un run est toujours attribué.** `creer_run` résout l'auteur d'office quand la
commande ne le donne pas, et la colonne est `NOT NULL` : une couche
interprétative anonyme ne se discute pas, elle se subit. Voir
`database/auteur.py`.
"""

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from database.auteur import resoudre as resoudre_auteur
from database.models import Run

SEGMENTATION = "segmentation"
ANALYSE = "analyse"
DOUBLONS = "doublons"
ANONYMISATION = "anonymisation"
# Une représentation vectorielle dépend d'un modèle, de sa version et de la
# façon dont le texte lui a été découpé : c'est une couche interprétative comme
# les autres, avec son run. Le modèle et la dimension vont dans `parameters`.
EMBEDDINGS = "embeddings"
# Ce qu'est une doléance — genre de document, genre d'auteur. Des règles de
# forme, donc une lecture datée et révisable, pas un fait du corpus.
TYPOLOGIE = "typologie"
# La transcription OCR d'une page dépend du modèle, du rendu et de la consigne :
# couche 3 du plan, une lecture de l'image qui se versionne comme les autres
# (`extraction/with_ocr/`, table `page_transcription`).
TRANSCRIPTION = "transcription"
GENRES = (
    SEGMENTATION,
    ANALYSE,
    DOUBLONS,
    ANONYMISATION,
    EMBEDDINGS,
    TYPOLOGIE,
    TRANSCRIPTION,
)


def creer_run(
    session: Session,
    genre: str,
    *,
    label: str,
    source: str | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
    parameters: dict[str, Any] | None = None,
    corpus: str | None = None,
    author: str | None = None,
    notes: str | None = None,
    actif: bool = True,
) -> Run:
    """Enregistre un run et, par défaut, en fait le run servi.

    Args:
        session: session ouverte sur la base.
        genre: ``SEGMENTATION`` ou ``ANALYSE``.
        label: nom court lisible, affiché à l'utilisateur.
        source: dossier de livraison ou module producteur.
        model: modèle LLM ou OCR employé, s'il y en a un.
        prompt_version: version du prompt, pour les runs LLM.
        parameters: seuils et configuration tels qu'appliqués.
        corpus: ce sur quoi le run a tourné.
        author: humain ou machine à l'origine du run ; résolu d'office s'il
            n'est pas donné (voir `database/auteur.py`).
        notes: tout ce qui aide à relire le run plus tard.
        actif: en faire le run servi par défaut pour son genre.

    Returns:
        Le run créé, déjà `flush` (son id est attribué).

    Raises:
        ValueError: si le genre est inconnu.
        AuteurInconnu: si aucune source ne nomme l'auteur. Un run non attribué
            ne se discute pas : la colonne est `NOT NULL` depuis le
            2026-09-10 et cette fonction est le seul chemin qui l'écrit.
    """
    if genre not in GENRES:
        raise ValueError(f"genre inconnu : {genre!r} (attendu : {', '.join(GENRES)})")

    run = Run(
        kind=genre,
        label=label,
        source=source,
        model=model,
        prompt_version=prompt_version,
        parameters=parameters,
        corpus=corpus,
        author=resoudre_auteur(author),
        notes=notes,
        active=False,
    )
    session.add(run)
    session.flush()
    if actif:
        activer_run(session, run)
    return run


def activer_run(session: Session, run: Run) -> None:
    """Fait de ce run celui servi par défaut pour son genre.

    Désactive les autres du même genre d'abord : la base impose un seul run
    actif par genre (index unique partiel), l'ordre n'est donc pas négociable.
    """
    session.execute(
        update(Run)
        .where(Run.kind == run.kind, Run.id != run.id)
        .values(active=False)
    )
    session.flush()
    run.active = True
    session.flush()


def run_actif(session: Session, genre: str) -> Run | None:
    """Le run servi par défaut pour ce genre, ou ``None`` s'il n'y en a pas.

    ``None`` est un état normal : une base fraîchement migrée n'a pas encore de
    découpage ni de livraison. Les lectures doivent le traiter comme « aucune
    donnée de cette couche », pas comme une erreur.
    """
    return session.scalars(
        select(Run).where(Run.kind == genre, Run.active.is_(True))
    ).first()


def id_run_actif(session: Session, genre: str) -> int | None:
    """Id du run actif pour ce genre, raccourci pour filtrer une requête."""
    run = run_actif(session, genre)
    return run.id if run is not None else None


def run_par_source(session: Session, genre: str, source: str) -> Run | None:
    """Le run le plus récent produit depuis cette source.

    Recharger deux fois la même livraison doit la mettre à jour, pas fabriquer
    une grille de plus : c'est la source qui identifie la livraison.
    """
    return session.scalars(
        select(Run)
        .where(Run.kind == genre, Run.source == source)
        .order_by(Run.id.desc())
    ).first()


def runs(session: Session, genre: str | None = None) -> list[Run]:
    """Tous les runs, du plus récent au plus ancien."""
    requete = select(Run).order_by(Run.id.desc())
    if genre is not None:
        requete = requete.where(Run.kind == genre)
    return list(session.scalars(requete))
