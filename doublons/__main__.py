"""Repère les doléances au texte quasi identique.

    uv run python -m doublons --auteur "prénom nom"
    uv run python -m doublons --seuil 0.7 --auteur "prénom nom"

Chaque exécution crée un run de genre `doublons` (`database/runs.py`) : le
regroupement dépend d'un seuil, deux seuils donnent deux lectures du corpus, et
elles doivent pouvoir coexister.
"""

import argparse
import sys

from sqlalchemy.orm import Session

from database.db import check_connection, get_engine
from database.models import DuplicateGroup
from database.runs import DOUBLONS, SEGMENTATION, creer_run, run_actif
from doublons.empreintes import BANDES, TAILLE_FRAGMENT, TAILLE_SIGNATURE
from doublons.groupes import SEUIL, SEUIL_PLANCHER, grouper
from doublons.persistance import (
    communes_des_doleances,
    enregistrer,
    lire_doleances,
)

GROUPES_MONTRES = 10


def main(seuil: float = SEUIL, auteur: str | None = None) -> int:
    engine = get_engine()
    check_connection(engine)

    with Session(engine) as session:
        decoupage = run_actif(session, SEGMENTATION)
        if decoupage is None:
            print(
                "Aucun découpage servi : les doublons se cherchent entre "
                "doléances (uv run python -m segmentation).",
                file=sys.stderr,
            )
            return 1

        if seuil < SEUIL_PLANCHER:
            print(
                f"seuil {seuil} sous le plancher {SEUIL_PLANCHER} : le filtre de "
                "paires candidates\nne descend pas si bas, le résultat serait "
                "silencieusement incomplet.\nÉlargir les bandes plutôt que "
                "baisser le seuil (doublons/empreintes.py).",
                file=sys.stderr,
            )
            return 1

        textes = lire_doleances(session, decoupage.id)
        if not textes:
            print("Aucune doléance à comparer.", file=sys.stderr)
            return 1

        groupes = grouper(textes, seuil)
        communes = communes_des_doleances(session, decoupage.id)

        run = creer_run(
            session,
            DOUBLONS,
            label=f"seuil {seuil}",
            source="doublons/",
            parameters={
                "seuil": seuil,
                "taille_fragment": TAILLE_FRAGMENT,
                "taille_signature": TAILLE_SIGNATURE,
                "bandes": BANDES,
                "run_segmentation": decoupage.id,
            },
            corpus=f"{len(textes)} doléance(s) · découpage #{decoupage.id}",
            author=auteur,
        )
        run_auteur = run.author
        groupees = enregistrer(session, run.id, groupes, communes)
        session.commit()

        plus_larges = (
            session.query(DuplicateGroup)
            .filter(DuplicateGroup.run_id == run.id)
            .order_by(DuplicateGroup.cities.desc(), DuplicateGroup.size.desc())
            .limit(GROUPES_MONTRES)
            .all()
        )
        apercu = [(g.size, g.cities, g.similarity_min) for g in plus_larges]

    part = groupees / len(textes)
    print(f"run de déduplication créé · seuil {seuil}")
    print(f"  {len(textes)} doléance(s) comparée(s)")
    print(f"  {len(groupes)} groupe(s) · {groupees} doléance(s) groupée(s) ({part:.0%})")
    if groupes:
        uniques = len(textes) - groupees + len(groupes)
        print(f"  textes distincts si un groupe compte pour un : {uniques}")
        print("\n  Groupes touchant le plus de communes :")
        for taille, communes_touchees, similarite in apercu:
            print(
                f"    {taille:4d} doléance(s) · {communes_touchees:3d} commune(s) "
                f"· similarité min {similarite:.2f}"
            )
        print(
            "\n  Un texte présent dans plusieurs communes n'est pas du bruit : "
            "c'est une\n  campagne organisée, ce qui est autre chose qu'une "
            "écriture individuelle.\n  Les groupes sont conservés, pas écrasés."
        )
    print(f"\nrun attribué à : {run_auteur}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--seuil", type=float, default=SEUIL, help=f"similarité minimale (défaut : {SEUIL})"
    )
    parser.add_argument(
        "--auteur",
        help="qui lance cette déduplication (défaut : la configuration git du dépôt)",
    )
    args = parser.parse_args()
    sys.exit(main(args.seuil, args.auteur))
