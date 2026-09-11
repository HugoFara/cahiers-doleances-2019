"""Charge une grille de thèmes écrite à la main — sans modèle, sans détections.

Une livraison d'analyse vient avec ses détections ; une grille de cadrage vient
seule. C'est le cas de « cadrage gouvernemental 2019 » (`grilles/`), qui
reproduit les quatre thèmes et les questions de la Lettre aux Français du
13 janvier 2019 : le plan la demande précisément pour que ce cadrage soit
visible et discutable, au lieu d'être la référence implicite de toute lecture.

Le fichier a la forme du `taxonomy.json` d'une livraison (`topics`, avec `id`,
`name`, `description`, `parent`), plus un `label` et une `source` qui disent
d'où la grille vient. Il devient un run de genre `analyse`, **non actif** par
défaut : sans détections, il n'a rien à servir, mais il apparaît dans le
sélecteur de l'app et `taxonomie/` peut le comparer aux autres.

Utilisation :
    uv run python -m analyse.grille analyse/grilles/cadrage_gouvernemental_2019.json
    uv run python -m analyse.grille <fichier> --activer
"""

import argparse
import json
from pathlib import Path

from sqlalchemy.orm import Session

from analyse.load_analysis import charger_topics, rattacher_parents
from database.db import check_connection, get_engine
from database.models import Run
from database.runs import ANALYSE, activer_run, creer_run, run_par_source

CLES_REQUISES = ("id", "name", "description", "parent")


def lire_grille(fichier: Path) -> dict:
    """Le fichier, vérifié : un label, une source, des thèmes qui se tiennent.

    Raises:
        ValueError: clé manquante, identifiant en double, ou parent inconnu —
            une grille de cadrage se relit à la main, elle ne se répare pas
            au chargement.
    """
    grille = json.loads(fichier.read_text(encoding="utf-8"))
    for cle in ("label", "source", "topics"):
        if cle not in grille:
            raise ValueError(f"{fichier.name} : clé « {cle} » absente")
    topics = grille["topics"]
    if not topics:
        raise ValueError(f"{fichier.name} : aucun thème")
    ids: set[str] = set()
    for t in topics:
        manquantes = [c for c in CLES_REQUISES if c not in t]
        if manquantes:
            raise ValueError(f"{fichier.name} : thème {t.get('id')!r} sans {manquantes}")
        if t["id"] in ids:
            raise ValueError(f"{fichier.name} : identifiant en double « {t['id']} »")
        ids.add(t["id"])
        t.setdefault("level", 0)
        t.setdefault("validated", False)
    for t in topics:
        if t["parent"] is not None and t["parent"] not in ids:
            raise ValueError(f"{fichier.name} : « {t['id']} » a pour parent inconnu « {t['parent']} »")
    reference = grille.get("reference")
    if reference is not None:
        # une distribution de référence : ce que la source de la grille a
        # mesuré chez elle, pour comparer — chaque part vise un thème
        for cle in ("titre", "source", "parts"):
            if cle not in reference:
                raise ValueError(f"{fichier.name} : référence sans « {cle} »")
        inconnus = sorted(set(reference["parts"]) - ids)
        if inconnus:
            raise ValueError(f"{fichier.name} : la référence vise des thèmes inconnus {inconnus}")
    return grille


def resoudre_run(session: Session, fichier: Path, grille: dict, *, auteur: str | None) -> Run:
    """Le run de cette grille : le sien si le fichier a déjà été chargé, un neuf sinon."""
    source = str(fichier)
    existant = run_par_source(session, ANALYSE, source)
    if existant is not None:
        print(f"grille reprise : run #{existant.id} « {existant.label} »")
        return existant
    provenance = grille["source"]
    run = creer_run(
        session,
        ANALYSE,
        label=grille["label"],
        source=source,
        model=None,
        parameters={"topics": len(grille["topics"]), "reference": grille.get("reference")},
        corpus="aucune détection : grille de cadrage",
        author=auteur,
        notes=f"{provenance.get('titre', '')} — {provenance.get('url', '')}".strip(" —"),
        actif=False,
    )
    print(f"grille créée : run #{run.id} « {run.label} »")
    return run


def charger(session: Session, fichier: Path, *, auteur: str | None = None, activer: bool = False) -> Run:
    grille = lire_grille(fichier)
    run = resoudre_run(session, fichier, grille, auteur=auteur)
    ids = charger_topics(session, grille["topics"], run.id)
    orphelins = rattacher_parents(session, grille["topics"], ids, run.id)
    assert orphelins == 0, "lire_grille a vérifié les parents"
    if activer:
        activer_run(session, run)
    racines = sum(1 for t in grille["topics"] if t["parent"] is None)
    print(f"{len(ids)} thèmes, dont {racines} racines · run {'actif' if run.active else 'non actif'}")
    return run


def main(fichier: Path, *, auteur: str | None = None, activer: bool = False) -> None:
    engine = get_engine()
    check_connection(engine)
    with Session(engine) as session:
        run = charger(session, fichier, auteur=auteur, activer=activer)
        run_auteur = run.author
        session.commit()
    print(f"run attribué à : {run_auteur}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Charge une grille de thèmes écrite à la main.")
    parser.add_argument("fichier", type=Path, help="fichier JSON de la grille (voir analyse/grilles/)")
    parser.add_argument("--auteur", help="qui charge la grille (défaut : la configuration git du dépôt)")
    parser.add_argument(
        "--activer", action="store_true",
        help="en faire la grille servie par l'app (par défaut elle est seulement listée)",
    )
    args = parser.parse_args()
    main(args.fichier, auteur=args.auteur, activer=args.activer)
