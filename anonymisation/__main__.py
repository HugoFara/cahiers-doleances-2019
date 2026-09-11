"""Repère les passages personnels des doléances.

    uv run python -m anonymisation --auteur "prénom nom"
    uv run python -m anonymisation --ner           # + entités nommées (extra ner)

**Ce n'est pas une anonymisation.** La passe repère des formes — courriels,
téléphones, IBAN, adresses, noms marqués par une civilité ou posés en signature.
Avec `--ner`, un modèle de reconnaissance d'entités nommées, en local, y ajoute
les noms cités au fil du texte sans marqueur. Le **rappel reste inconnu** dans
les deux cas : il ne se mesure que sur un échantillon annoté à la main, qui
n'existe pas. Rien ici ne permet de déclarer une doléance publiable.
"""

import argparse
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from anonymisation.ner import MODELE as MODELE_NER
from anonymisation.passe import detecter_tout, lire_doleances
from database.db import check_connection, get_engine
from database.models import PiiSpan
from database.runs import ANONYMISATION, SEGMENTATION, creer_run, run_actif

AVERTISSEMENT = """
  ⚠ Ceci n'est pas une anonymisation.
    · sans --ner, les noms non marqués (« j'ai parlé à Bernard ») ne sont pas
      repérés ; avec, ils le sont par un modèle dont le rappel n'est pas mesuré ;
    · le rappel de cette passe est INCONNU — il se mesure sur un échantillon
      annoté à la main, qui reste à constituer ;
    · rien n'est occulté sur les images : sans coordonnées de ligne, le scan
      reste en clair même quand la transcription est caviardée.
    Aucun de ces passages ne permet de déclarer une doléance publiable."""


def main(auteur: str | None = None, ner: str | None = None) -> int:
    engine = get_engine()
    check_connection(engine)
    entites = None
    if ner:
        from anonymisation.ner import EntitesNommees

        entites = EntitesNommees(modele=ner)

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
            label="formes, signatures et entités nommées"
            if entites
            else "formes et signatures",
            source="anonymisation/",
            parameters={
                "detecteurs": "regex + signature" + (" + ner" if entites else ""),
                "ner": entites.modele if entites else None,
                "seuils_ner": entites.seuils if entites else None,
            },
            corpus=f"{len(textes)} doléance(s) · découpage #{decoupage.id}",
            author=auteur,
            notes=(
                "Formes, signatures et entités nommées (modèle local, CPU). "
                "Le rappel n'est pas mesuré."
                if entites
                else "Passe de formes uniquement. Les noms non marqués ne sont pas "
                "repérés et le rappel n'est pas mesuré."
            ),
        )
        run_auteur = run.author
        session.commit()
        comptes = detecter_tout(session, run.id, textes, entites)
        session.commit()

        touchees = session.execute(
            select(func.count(func.distinct(PiiSpan.doleance_id))).where(
                PiiSpan.run_id == run.id
            )
        ).scalar()

    total = sum(comptes.values())
    print(f"run d'anonymisation créé · {len(textes)} doléance(s) examinée(s)")
    print(
        f"  {total} passage(s) repéré(s) dans {touchees} doléance(s) "
        f"({touchees / len(textes):.0%})"
    )
    for genre, n in sorted(comptes.items(), key=lambda c: -c[1]):
        print(f"    {genre:14} {n:5d}")
    print(AVERTISSEMENT)
    print(f"\nrun attribué à : {run_auteur}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--auteur",
        help="qui lance cette passe (défaut : la configuration git du dépôt)",
    )
    parser.add_argument(
        "--ner",
        nargs="?",
        const=MODELE_NER,
        default=None,
        metavar="MODELE",
        help=f"ajouter la reconnaissance d'entités nommées (défaut : {MODELE_NER}) ; "
        "demande l'extra `ner`",
    )
    args = parser.parse_args()
    sys.exit(main(args.auteur, args.ner))
