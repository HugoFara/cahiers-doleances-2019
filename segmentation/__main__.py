"""Découpe les cahiers en doléances, sur leur texte de lecture.

Le texte lu est celui de `database/pages.py` : la transcription du run
`transcription` actif quand la page en a une, le squelette sinon. Le découpage
est rapporté à un **run** (`database/runs.py`) : il est interprétatif, il doit
donc être versionné, attribué, et comparable à un autre — et il note quel run
de transcription il a lu.

    uv run python -m segmentation
        complète le run de découpage actif — les cahiers qu'il ne couvre pas
        encore — et en crée un s'il n'y en a pas.

    uv run python -m segmentation --nouveau-run "règles v2"
        crée un run et y redécoupe tout le corpus. Le run précédent reste en
        base, intact et comparable : on ne détruit plus un découpage pour en
        essayer un autre.
"""

import argparse
import sys

from sqlalchemy.orm import Session

from database.db import check_connection, get_engine
from database.pages import TRANSCRIPTION_ACTIVE
from database.runs import SEGMENTATION, TRANSCRIPTION, creer_run, run_actif
from segmentation import config
from segmentation.persistance import (
    cahiers_deja_decoupes,
    enregistrer_cahier,
    grouper_par_cahier,
    lire_pages,
)


def parametres_appliques() -> dict:
    """Les seuils du découpage, tels qu'appliqués, pour être relus plus tard."""
    return {
        "signaux": ["date", "apostrophe", "cloture", "separateur", "numerotation"],
        "min_caracteres_doleance": config.MIN_CARACTERES_DOLEANCE,
        "lignes_signature": config.LIGNES_SIGNATURE,
        "longueur_ligne_signature": config.LONGUEUR_LIGNE_SIGNATURE,
    }


def main(
    nouveau_run: str | None = None,
    auteur: str | None = None,
) -> int:
    engine = get_engine()
    check_connection(engine)

    with Session(engine) as session:
        lues = lire_pages(session)
        cahiers = grouper_par_cahier(lues)
        if not cahiers:
            print(
                "Aucune page à découper. La table page_extraction est-elle remplie "
                "(uv run python -m extraction.without_ocr) ?",
                file=sys.stderr,
            )
            return 1

        pages_lues = sum(len(pages) for pages in cahiers.values())
        transcrites = sum(1 for p in lues if p.source == TRANSCRIPTION_ACTIVE)
        run_ocr = run_actif(session, TRANSCRIPTION)
        run = None if nouveau_run else run_actif(session, SEGMENTATION)
        if run is None:
            # Le découpage note ce qu'il a lu : sans le run de transcription,
            # deux découpages du « même » corpus ne seraient pas comparables.
            run = creer_run(
                session,
                SEGMENTATION,
                label=nouveau_run or "découpage par signaux de texte",
                source="segmentation/",
                parameters=parametres_appliques()
                | {"run_transcription": run_ocr.id if run_ocr else None},
                corpus=f"{pages_lues} page(s) · {len(cahiers)} cahier(s) · "
                + (
                    f"{transcrites} transcrite(s) (run #{run_ocr.id})"
                    if run_ocr
                    else "pages manuscrites écartées"
                ),
                author=auteur,
            )
            print(f"run de découpage créé : #{run.id} « {run.label} »")
        else:
            print(f"run de découpage actif : #{run.id} « {run.label} »")

        deja = cahiers_deja_decoupes(session, run.id)
        traites = ignores = total = 0
        for pdf_name, pages in cahiers.items():
            if pdf_name in deja:
                ignores += 1
                continue
            total += len(enregistrer_cahier(session, pdf_name, pages, run.id))
            traites += 1

        # Lus avant le commit : la session expire ses objets ensuite, et le run
        # devient inaccessible une fois sortie du `with`.
        run_auteur = run.author
        session.commit()

    print(f"{traites} cahier(s) découpé(s) · {total} doléance(s) écrite(s)")
    if ignores:
        print(
            f"{ignores} cahier(s) déjà couvert(s) par ce run, ignoré(s) — "
            "--nouveau-run pour redécouper tout le corpus ailleurs"
        )
    print(f"run attribué à : {run_auteur}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--nouveau-run",
        metavar="LABEL",
        help="créer un run de découpage et y rejouer tout le corpus",
    )
    parser.add_argument(
        "--auteur",
        help="qui lance ce découpage (défaut : la configuration git du dépôt)",
    )
    args = parser.parse_args()
    sys.exit(main(args.nouveau_run, args.auteur))
