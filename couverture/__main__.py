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
from database.models import Contribution, PageExtraction
from database.pages import transcriptions_actives
from insee.cog import Commune, lire, populations_sans_double_compte

SEUILS_TESTES = [0.1, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5]
SEUIL_EN_SERVICE = 0.3
COMMUNES_MONTREES = 10


def barre(part: int, total: int, largeur: int = 40) -> str:
    return "█" * (part * largeur // max(1, total))


def referentiel() -> dict[str, Commune]:
    """Le référentiel INSEE, ou rien s'il n'est pas lisible.

    Rien : la pondération et les noms officiels disparaissent du rapport plutôt
    que de le faire échouer. Le reste des mesures ne dépend pas de l'INSEE.
    """
    try:
        return lire()
    except (OSError, KeyError):
        return {}


def codes_communes(session: Session) -> dict[int, str]:
    """``{contribution_id: code INSEE}``, vide si le rattachement n'a pas tourné.

    Vide, `mesurer` retombe sur les graphies : le compte de communes est alors
    faux d'un tiers. Le rapport le signale plutôt que de laisser croire.
    """
    lignes = session.execute(
        select(Contribution.id, Contribution.city_code).where(
            Contribution.city_code.is_not(None)
        )
    ).all()
    return dict(lignes)


def rapport(
    pages: list,
    communes: dict[int, str] | None = None,
    habitants: dict[str, int] | None = None,
    noms: dict[str, str] | None = None,
    transcrites: set[int] | None = None,
) -> dict:
    """Assemble les mesures en une structure sérialisable."""
    couverture = mesurer(pages, communes, habitants, noms, transcrites)
    return {
        "mesure_le": datetime.now(UTC).date().isoformat(),
        "seuil_needs_ocr": SEUIL_EN_SERVICE,
        "pages": {
            "total": couverture.pages.total,
            "ecartees": couverture.pages.ecartes,
            "transcrites": couverture.transcrites,
        },
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
        "communes_identifiees_par": "code INSEE" if communes else "graphie",
        "habitants": (
            None
            if couverture.habitants is None
            else {
                "total": couverture.habitants.total,
                "communes_muettes": couverture.habitants.ecartes,
            }
        ),
        "distribution_qualite": distribution_qualite(pages),
        "sensibilite_seuil": {
            str(seuil): part.ecartes
            for seuil, part in sensibilite_seuil(pages, SEUILS_TESTES).items()
        },
    }


def afficher(
    pages: list,
    communes: dict[int, str] | None = None,
    habitants: dict[str, int] | None = None,
    noms: dict[str, str] | None = None,
    transcrites: set[int] | None = None,
) -> None:
    couverture = mesurer(pages, communes, habitants, noms, transcrites)
    print("Part du corpus écartée : pages `needs_ocr` sans transcription\n")
    if not communes:
        print(
            "  ⚠ communes comptées par graphie : le rattachement INSEE n'a pas "
            "tourné.\n    Le compte de communes est sous-estimé d'environ un "
            "tiers (uv run python -m insee rattacher).\n"
        )
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

    if couverture.habitants is None:
        print(
            "\n  ⚠ pas de pondération par population : le référentiel INSEE "
            "n'est pas\n    chargé (uv run python -m insee cog)."
        )

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
        communes = codes_communes(session)
        transcrites = set(transcriptions_actives(session))
    codes = set(communes.values())
    communes_insee = referentiel()
    habitants = populations_sans_double_compte(codes, communes_insee)
    noms = {code: communes_insee[code].nom for code in codes if code in communes_insee}

    if not pages:
        print(
            "Aucune page en base. Lancer l'extraction "
            "(uv run python -m extraction.without_ocr) ?",
            file=sys.stderr,
        )
        return 1

    afficher(pages, communes, habitants, noms, transcrites)
    if sortie:
        sortie.parent.mkdir(parents=True, exist_ok=True)
        sortie.write_text(
            json.dumps(
                rapport(pages, communes, habitants, noms, transcrites),
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        print(f"\n  rapport -> {sortie}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--json", type=Path, dest="sortie", help="écrire aussi le rapport en JSON"
    )
    args = parser.parse_args()
    sys.exit(main(args.sortie))
