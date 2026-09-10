"""Repère les passages personnels des doléances.

    uv run python -m anonymisation --auteur "prénom nom"

**Ce n'est pas une anonymisation.** La passe repère des formes — courriels,
téléphones, IBAN, adresses, noms marqués par une civilité ou posés en signature.
Elle ne repère pas un nom cité au fil du texte sans marqueur, qui est le cas le
plus fréquent et demande une reconnaissance d'entités nommées. Et son **rappel
est inconnu** : il ne se mesure que sur un échantillon annoté à la main, qui
n'existe pas. Rien ici ne permet de déclarer une doléance publiable.
"""

import argparse
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from anonymisation.passe import detecter_tout, lire_doleances
from database.db import check_connection, get_engine
from database.models import PiiSpan
from database.runs import ANONYMISATION, SEGMENTATION, creer_run, run_actif

AVERTISSEMENT = """
  ⚠ Ceci n'est pas une anonymisation.
    · les noms non marqués (« j'ai parlé à Bernard ») ne sont pas repérés :
      il y faut une reconnaissance d'entités nommées, qui n'est pas ici ;
    · le rappel de cette passe est INCONNU — il se mesure sur un échantillon
      annoté à la main, qui reste à constituer ;
    · rien n'est occulté sur les images : sans coordonnées de ligne, le scan
      reste en clair même quand la transcription est caviardée.
    Aucun de ces passages ne permet de déclarer une doléance publiable."""


def main(auteur: str | None = None) -> int:
    engine = get_engine()
    check_connection(engine)

    with Session(engine) as session:
        decoupage = run_actif(session, SEGMENTATION)
        if decoupage is None:
            print(
                "Aucun découpage servi : les passages se repèrent dans les "
                "doléances (uv run python -m segmentation).",
                file=sys.stderr,
            )
            return 1

        textes = lire_doleances(session, decoupage.id)
        if not textes:
            print("Aucune doléance à examiner.", file=sys.stderr)
            return 1

        run = creer_run(
            session,
            ANONYMISATION,
            label="formes et signatures",
            source="anonymisation/",
            parameters={"detecteurs": "regex + signature", "ner": None},
            corpus=f"{len(textes)} doléance(s) · découpage #{decoupage.id}",
            author=auteur,
            notes=(
                "Passe de formes uniquement. Les noms non marqués ne sont pas "
                "repérés et le rappel n'est pas mesuré."
            ),
        )
        comptes = detecter_tout(session, run.id, textes)
        session.commit()

        touchees = session.execute(
            select(func.count(func.distinct(PiiSpan.doleance_id))).where(
                PiiSpan.run_id == run.id
            )
        ).scalar()

    total = sum(comptes.values())
    print(f"run d'anonymisation créé · {len(textes)} doléance(s) examinée(s)")
    print(f"  {total} passage(s) repéré(s) dans {touchees} doléance(s) "
          f"({touchees / len(textes):.0%})")
    for genre, n in sorted(comptes.items(), key=lambda c: -c[1]):
        print(f"    {genre:14} {n:5d}")
    print(AVERTISSEMENT)
    if auteur is None:
        print("\nrun sans auteur : renseigner --auteur avant publication")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--auteur", help="qui lance cette passe")
    args = parser.parse_args()
    sys.exit(main(args.auteur))
