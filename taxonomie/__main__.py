"""Mesure la grille de thèmes servie.

    uv run python -m taxonomie
    uv run python -m taxonomie --run 4

Aucune de ces mesures ne dit « la grille est bonne ». Elles disent ce qu'elle
fait, ce qui permet de comparer deux grilles et de savoir dans quel sens on va —
ce qui manquait aux 32 passes successives de `factorize` du RECIPE de
topic-builder.
"""

import argparse
import sys
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.db import check_connection, get_engine
from database.models import Doleance, Instance, PageExtraction, Run, Topic
from database.runs import ANALYSE, run_actif
from taxonomie.mesures import couverture, hierarchie, reutilisation

TETE = 8


def _histogramme(compteur, maximum: int = 6) -> list[str]:
    """Distribution ramassée : 1, 2, … puis « et plus »."""
    total = sum(1 for _ in compteur)
    if not total:
        return []
    tranches = defaultdict(int)
    for valeur in compteur.values():
        tranches[min(valeur, maximum)] += 1
    lignes = []
    for cle in sorted(tranches):
        libelle = f"{cle}" if cle < maximum else f"{cle} et plus"
        part = tranches[cle] / total
        lignes.append(f"    {libelle:>10} : {tranches[cle]:5d}  ({part:.0%})")
    return lignes


def textes_des_documents(session: Session, run_id: int) -> dict[str, str]:
    """Texte des documents visés par les instances de ce run.

    Les instances portent soit une doléance, soit une contribution : la
    couverture se mesure contre le texte réellement soumis à l'analyse.
    Une livraison dont aucune instance n'est rattachée ne peut pas être mesurée
    ici — c'est le cas des livraisons antérieures à `export_dataset.py`.
    """
    textes: dict[str, str] = {}

    doleances = session.execute(
        select(Instance.external_doc_id, Doleance.text)
        .join(Doleance, Instance.doleance_id == Doleance.id)
        .where(Instance.run_id == run_id)
    ).all()
    textes.update({identifiant: texte or "" for identifiant, texte in doleances})

    pages = session.execute(
        select(Instance.external_doc_id, PageExtraction.text)
        .join(PageExtraction, Instance.contribution_id == PageExtraction.contribution_id)
        .where(Instance.run_id == run_id, Instance.doleance_id.is_(None))
    ).all()
    par_document: dict[str, list[str]] = defaultdict(list)
    for identifiant, texte in pages:
        if texte:
            par_document[identifiant].append(texte)
    textes.update({d: "\n".join(t) for d, t in par_document.items()})
    return textes


def main(run_choisi: int | None = None) -> int:
    engine = get_engine()
    check_connection(engine)

    with Session(engine) as session:
        if run_choisi is None:
            run = run_actif(session, ANALYSE)
            if run is None:
                print("Aucune grille servie à mesurer.", file=sys.stderr)
                return 1
            run_id, label = run.id, run.label
        else:
            run_id = run_choisi
            choisi = session.get(Run, run_id)
            a_des_themes = session.execute(
                select(Topic.run_id).where(Topic.run_id == run_id).limit(1)
            ).scalar()
            if choisi is None or not a_des_themes:
                print(f"Aucun thème pour le run #{run_id}.", file=sys.stderr)
                return 1
            label = choisi.label

        themes = session.execute(
            select(Topic.id, Topic.parent_id, Topic.name).where(Topic.run_id == run_id)
        ).all()
        detections = session.execute(
            select(Instance.topic_id, Instance.external_doc_id).where(
                Instance.run_id == run_id
            )
        ).all()
        textes = textes_des_documents(session, run_id)
        verbatims: dict[str, list[str]] = defaultdict(list)
        for identifiant, verbatim in session.execute(
            select(Instance.external_doc_id, Instance.verbatim).where(
                Instance.run_id == run_id, Instance.verbatim.is_not(None)
            )
        ).all():
            verbatims[identifiant].append(verbatim)

    if not themes:
        print("Grille vide.", file=sys.stderr)
        return 1

    print(f"grille servie : #{run_id} « {label} »\n")

    usage = reutilisation(
        [(str(t), str(d)) for t, d in detections if t is not None and d is not None],
        [str(identifiant) for identifiant, _, _ in themes],
    )
    print("Réutilisation")
    for ligne in usage.resume():
        print(f"  {ligne}")
    print("\n  documents par thème :")
    print("\n".join(_histogramme(usage.documents_par_theme)))
    print("\n  thèmes par document :")
    print("\n".join(_histogramme(usage.themes_par_document)))

    arbre = hierarchie([
        (str(identifiant), str(pere) if pere is not None else None, nom or "")
        for identifiant, pere, nom in themes
    ])
    print("\nHiérarchie")
    for ligne in arbre.resume():
        print(f"  {ligne}")

    print("\nCouverture du texte (« hors grille »)")
    if not textes:
        print(
            "  non mesurable : aucune instance de ce run n'est rattachée à un\n"
            "  document de notre corpus. C'est le cas des livraisons antérieures\n"
            "  à export_dataset.py, dont les identifiants désignent un autre corpus."
        )
    else:
        mesure = couverture(textes, dict(verbatims))
        for ligne in mesure.resume():
            print(f"  {ligne}")
        pires = sorted(mesure.details, key=lambda d: (d[2] / d[1]) if d[1] else 0)[:TETE]
        print("\n  documents les moins couverts :")
        for identifiant, taille, couvert in pires:
            part = couvert / taille if taille else 0.0
            print(f"    {identifiant:>12} : {part:4.0%} de {taille} caractères")

    print(
        "\n  Un thème attesté par un seul document est la paraphrase de ce\n"
        "  document, pas un thème. Le « hors grille » est le chiffre qui manque\n"
        "  à tout comptage : sans lui, « 34 % parlent de fiscalité » ne dit pas\n"
        "  sur quelle part du corpus il porte."
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--run", type=int, help="grille à mesurer (défaut : celle servie)")
    args = parser.parse_args()
    sys.exit(main(args.run))
