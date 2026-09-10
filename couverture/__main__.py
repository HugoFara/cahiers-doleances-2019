"""Chiffre ce que le corpus analysé laisse dehors.

    uv run python -m couverture
    uv run python -m couverture --json data/couverture.json

Le rapport ne contient que des compteurs — jamais le texte des cahiers — il est
donc partageable tel quel. Les noms de communes sans aucune page lisible en font
partie : ce sont des données publiques, et c'est précisément l'information qu'il
faut afficher à côté de tout comptage.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from couverture.mesures import distribution_qualite, mesurer, sensibilite_seuil
from database.db import check_connection, get_engine
from database.models import PageExtraction

SEUILS_TESTES = [0.1, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5]
SEUIL_EN_SERVICE = 0.3
COMMUNES_MONTREES = 10


def barre(part: int, total: int, largeur: int = 40) -> str:
    return "█" * (part * largeur // max(1, total))


def rapport(pages: list) -> dict:
    """Assemble les mesures en une structure sérialisable."""
    couverture = mesurer(pages)
    return {
        "mesure_le": datetime.now(UTC).date().isoformat(),
        "seuil_needs_ocr": SEUIL_EN_SERVICE,
        "pages": {"total": couverture.pages.total, "ecartees": couverture.pages.ecartes},
        "cahiers": {
            "total": couverture.cahiers.total,
            "touches": couverture.cahiers.ecartes,
            "entierement_ecartes": len(couverture.cahiers_muets),
        },
        "communes": {
            "total": couverture.communes.total,
            "touchees": couverture.communes.ecartes,
            "sans_aucune_page_lisible": len(couverture.communes_muettes),
            "muettes": couverture.communes_muettes,
        },
        "distribution_qualite": distribution_qualite(pages),
        "sensibilite_seuil": {
            str(seuil): part.ecartes
            for seuil, part in sensibilite_seuil(pages, SEUILS_TESTES).items()
        },
    }


def afficher(pages: list) -> None:
    couverture = mesurer(pages)
    print("Part du corpus écartée par le filtre `needs_ocr`\n")
    for ligne in couverture.resume():
        print(f"  {ligne}")

    print("\n  Distribution des scores de qualité :")
    for tranche, n in distribution_qualite(pages).items():
        print(f"    {tranche} : {n:6d}  {barre(n, len(pages))}")

    print(f"\n  Sensibilité au seuil (en service : {SEUIL_EN_SERVICE}) :")
    for seuil, part in sensibilite_seuil(pages, SEUILS_TESTES).items():
        ici = "  <- en service" if seuil == SEUIL_EN_SERVICE else ""
        print(f"    {seuil:.2f} -> {part.ecartes:6d} pages ({part.taux:.0%}){ici}")

    muettes = couverture.communes_muettes
    if muettes:
        print(f"\n  Communes sans aucune page lisible ({len(muettes)}) :")
        for nom in muettes[:COMMUNES_MONTREES]:
            print(f"    {nom}")
        if len(muettes) > COMMUNES_MONTREES:
            print(f"    … et {len(muettes) - COMMUNES_MONTREES} autres")

    print(
        "\n  Ces pages ne sont pas un déchet technique : c'est l'écriture "
        "manuscrite,\n  donc la contribution ordinaire. Ce taux doit accompagner "
        "tout comptage\n  tiré du corpus, sans quoi il se lit comme portant sur "
        "l'ensemble."
    )


def main(sortie: Path | None = None) -> int:
    engine = get_engine()
    check_connection(engine)
    with Session(engine) as session:
        pages = list(session.scalars(select(PageExtraction)))

    if not pages:
        print(
            "Aucune page en base. Lancer l'extraction "
            "(uv run python -m extraction.without_ocr) ?",
            file=sys.stderr,
        )
        return 1

    afficher(pages)
    if sortie:
        sortie.parent.mkdir(parents=True, exist_ok=True)
        sortie.write_text(json.dumps(rapport(pages), ensure_ascii=False, indent=2) + "\n")
        print(f"\n  rapport -> {sortie}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--json", type=Path, dest="sortie", help="écrire aussi le rapport en JSON"
    )
    args = parser.parse_args()
    sys.exit(main(args.sortie))
