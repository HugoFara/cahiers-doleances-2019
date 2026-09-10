"""Classe chaque doléance : genre de document, genre d'auteur.

    uv run python -m typologie
    uv run python -m typologie --auteur "prénom nom"

**Ce sont des règles de forme, pas un fait du corpus.** Elles lisent des
formules d'appel, des signatures, des marques de première personne. Elles ne
voient ni la mise en page, ni l'écriture, ni le papier — c'est-à-dire aucun des
indices sur lesquels un archiviste tranche réellement. Leur précision et leur
rappel ne sont pas mesurés, faute d'échantillon annoté : `confirmed` reste NULL
partout et attend une relecture humaine.

Ce qu'elles permettent malgré tout est ce que le plan leur demande : ne plus
compter ensemble un mot d'habitant, une motion de conseil municipal et le
courrier par lequel la mairie transmet le cahier.
"""

import argparse
import sys

from sqlalchemy.orm import Session

from database.db import check_connection, get_engine
from database.runs import DOUBLONS, SEGMENTATION, TYPOLOGIE, creer_run, run_actif
from typologie.classement import AUTEUR, SUPPORT
from typologie.passe import classer_tout, lire_doleances, lire_recopies

AVERTISSEMENT = """
  ⚠ Ces étiquettes sont des règles de forme, pas une description du support.
    · aucune ne lit la mise en page, l'écriture ni le papier — les vrais
      indices — mais seulement les formules présentes dans le texte ;
    · leur précision et leur rappel sont INCONNUS : il y faut un échantillon
      annoté à la main, qui reste à constituer ;
    · « indeterminé » est un résultat et non un défaut : une liste de
      revendications sans sujet grammatical ne dit pas qui l'écrit."""


def main(auteur: str | None = None) -> int:
    engine = get_engine()
    check_connection(engine)

    with Session(engine) as session:
        decoupage = run_actif(session, SEGMENTATION)
        if decoupage is None:
            print(
                "Aucun découpage servi : la typologie se pose sur les doléances "
                "(uv run python -m segmentation).",
                file=sys.stderr,
            )
            return 1

        textes = lire_doleances(session, decoupage.id)
        if not textes:
            print("Aucune doléance à classer.", file=sys.stderr)
            return 1

        dedup = run_actif(session, DOUBLONS)
        id_dedup = dedup.id if dedup else None
        recopies = lire_recopies(session, id_dedup)

        run = creer_run(
            session,
            TYPOLOGIE,
            label="règles de forme",
            source="typologie/",
            parameters={
                "run_segmentation": decoupage.id,
                "run_doublons": id_dedup,
                "regles": "formules positionnées + première personne",
            },
            corpus=f"{len(textes)} doléance(s) · découpage #{decoupage.id}",
            author=auteur,
            notes=(
                "Règles de forme uniquement. Ni la mise en page ni l'écriture ne "
                "sont lues, et aucune étiquette n'est vérifiée."
            ),
        )
        comptes = classer_tout(session, run.id, textes, recopies)
        run_auteur = run.author
        session.commit()

    print(f"run de typologie créé · {len(textes)} doléance(s) classée(s)")
    if recopies:
        print(f"  {len(recopies)} doléance(s) recopiée(s) dans plusieurs communes "
              f"(déduplication #{id_dedup})")
    else:
        print("  aucune déduplication servie : le support « lettre_type » "
              "n'est jamais conclu")
    for axe in (SUPPORT, AUTEUR):
        print(f"\n  {axe}")
        for valeur, n in comptes[axe].most_common():
            print(f"    {valeur:<14} {n:5d}  {n / len(textes):>4.0%}")
    print(AVERTISSEMENT)
    print(f"\nrun attribué à : {run_auteur}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--auteur",
        help="qui lance cette passe (défaut : la configuration git du dépôt)",
    )
    args = parser.parse_args()
    sys.exit(main(args.auteur))
