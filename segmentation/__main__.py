"""Découpe les cahiers de `page_extraction` en doléances.

Utilisation :
    uv run python -m segmentation              # découpe les cahiers pas encore traités
    uv run python -m segmentation --force      # redécoupe tout
"""

import argparse
import sys

from sqlalchemy.orm import Session

from database.db import check_connection, get_engine
from segmentation.persistance import (
    cahiers_deja_decoupes,
    enregistrer_cahier,
    grouper_par_cahier,
    lire_pages,
    oublier_cahier,
)


def main(force: bool = False, garder_pages_ocr: bool = False) -> int:
    engine = get_engine()
    check_connection(engine)

    with Session(engine) as session:
        cahiers = grouper_par_cahier(lire_pages(session, garder_pages_ocr))
        if not cahiers:
            print(
                "Aucune page à découper. La table page_extraction est-elle remplie "
                "(uv run python -m extraction.without_ocr) ?",
                file=sys.stderr,
            )
            return 1

        deja = cahiers_deja_decoupes(session)
        traites = ignores = total = 0
        for pdf_name, pages in cahiers.items():
            if pdf_name in deja:
                if not force:
                    ignores += 1
                    continue
                oublier_cahier(session, pdf_name)
            total += len(enregistrer_cahier(session, pdf_name, pages))
            traites += 1

        session.commit()

    print(f"{traites} cahier(s) découpé(s) · {total} doléance(s) écrite(s)")
    if ignores:
        print(f"{ignores} cahier(s) déjà découpé(s), ignoré(s) — --force pour rejouer")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--force", action="store_true", help="redécouper les cahiers déjà traités"
    )
    parser.add_argument(
        "--keep-ocr-pages",
        action="store_true",
        help="inclure les pages manuscrites (needs_ocr), du bruit par défaut écarté",
    )
    args = parser.parse_args()
    sys.exit(main(args.force, args.keep_ocr_pages))
