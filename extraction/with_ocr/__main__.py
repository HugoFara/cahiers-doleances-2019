"""Transcrire les pages par OCR : Mistral (API) ou Ollama (local).

`without_ocr` lit la couche texte des PDFs : elle donne les cahiers
dactylographiés, pas les manuscrits — 47 % des pages écartées, 37 communes
sans aucune page lisible. Cette commande rend l'image de la page et la fait
transcrire par un modèle OCR.

La passe est un run de genre `transcription` : backend, modèle, rendu,
consigne et périmètre y sont portés. Les transcriptions vont dans
`page_transcription` — le squelette (`page_extraction.text`) n'est pas
écrasé, deux passes coexistent et se comparent. `--run-id` reprend une passe
interrompue : les pages déjà transcrites du run sont sautées.

Exemples :
    uv run python -m extraction.with_ocr --limite 5     # essai, 5 pages
    uv run python -m extraction.with_ocr                # tout le manuscrit
    uv run python -m extraction.with_ocr --backend ollama --model glm-ocr
    uv run python -m extraction.with_ocr --run-id 3     # reprend le run 3
    uv run python -m extraction.with_ocr --batch --format jpeg  # moitié prix, en heures
"""

import argparse
import sys
import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tqdm import tqdm

from database.db import check_connection, get_engine
from database.models import PageTranscription, Run
from database.runs import TRANSCRIPTION
from extraction.with_ocr import batch as mode_batch
from extraction.with_ocr.backends import ErreurOcr, fabrique_backend
from extraction.with_ocr.config import OcrConfig
from extraction.with_ocr.normalize import normaliser
from extraction.with_ocr.persist import (
    PERIMETRES,
    enregistrer,
    etendre_perimetre,
    ouvrir_run,
    pages_a_transcrire,
)
from extraction.with_ocr.render import FORMATS, PdfIntrouvable, rendre_page
from extraction.with_ocr.settings import logger
from extraction.without_ocr.extract_text import wordfreq_quality_score


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="extraction.with_ocr",
        description="Transcrit les pages des cahiers par OCR (Mistral ou Ollama).",
    )
    p.add_argument(
        "--backend",
        choices=("mistral", "ollama"),
        default="mistral",
        help="modèle OCR employé (défaut : mistral)",
    )
    p.add_argument(
        "--model",
        default=None,
        help="nom du modèle (défaut : mistral-ocr-latest / glm-ocr)",
    )
    p.add_argument(
        "--perimetre",
        choices=PERIMETRES,
        default=None,
        help=(
            "manuscrit : pages needs_ocr (défaut) ; typé : le reste ; "
            "suspect : typé sous le seuil de qualité (formulaires remplis à "
            "la main) ; tout : le corpus entier. Avec --run-id, étend la passe "
            "à ce périmètre (le run note « manuscrit+suspect »)"
        ),
    )
    p.add_argument(
        "--limite",
        type=int,
        default=None,
        help="nombre maximal de pages — pour un essai",
    )
    p.add_argument(
        "--dpi",
        type=int,
        default=OcrConfig.DPI.value,
        help=f"résolution du rendu (défaut : {OcrConfig.DPI.value})",
    )
    p.add_argument(
        "--format",
        choices=FORMATS,
        default="png",
        help="format de l'image envoyée (défaut : png ; jpeg pèse dix fois moins)",
    )
    p.add_argument(
        "--batch",
        action="store_true",
        help=(
            "mistral seulement : passe par l'API batch — moitié prix, résultats "
            "en heures ; la commande attend et persiste au fil des lots"
        ),
    )
    p.add_argument(
        "--run-id",
        type=int,
        default=None,
        help="reprend une passe existante au lieu d'en ouvrir une nouvelle",
    )
    p.add_argument("--label", default=None, help="nom court du run")
    p.add_argument(
        "--auteur",
        default=None,
        help="auteur de la passe ; résolu d'office s'il manque (database/auteur.py)",
    )
    p.add_argument("--notes", default=None, help="notes libres sur le run")
    return p


def _run_existant(session: Session, run_id: int) -> Run | None:
    run = session.get(Run, run_id)
    if run is None:
        logger.error("run %d introuvable", run_id)
        return None
    if run.kind != TRANSCRIPTION:
        logger.error(
            "le run %d est de genre %r, pas %r", run_id, run.kind, TRANSCRIPTION
        )
        return None
    return run


def main(argv: list[str] | None = None) -> int:
    """Transcrit les pages du périmètre et persiste la passe.

    Returns:
        0 si toutes les pages ont été transcrites, 1 sinon.
    """
    args = parser().parse_args(argv)

    if args.batch and args.backend != "mistral":
        logger.error("--batch n'existe que pour le backend mistral")
        return 1
    engine = get_engine()
    check_connection(engine)
    backend = fabrique_backend(args.backend, args.model)

    with Session(engine) as session:
        if args.run_id is not None:
            run = _run_existant(session, args.run_id)
            if run is None:
                return 1
            parametres = run.parameters or {}
            perimetre = etendre_perimetre(session, run, args.perimetre)
            dpi = parametres.get("dpi", args.dpi)
            format = parametres.get("format", args.format)
            en_batch = args.batch or bool(mode_batch.lots_du_run(run))
            logger.info("reprise du run %d — %s", run.id, run.label)
        else:
            run = ouvrir_run(
                session,
                backend=args.backend,
                model=backend.model,
                dpi=args.dpi,
                format=args.format,
                batch=args.batch,
                perimetre=args.perimetre or "manuscrit",
                prompt=(
                    OcrConfig.OLLAMA_PROMPT.value if args.backend == "ollama" else None
                ),
                label=args.label,
                auteur=args.auteur,
                notes=args.notes,
            )
            session.commit()
            perimetre = args.perimetre or "manuscrit"
            dpi, format = args.dpi, args.format
            en_batch = args.batch

        pages = pages_a_transcrire(session, run, perimetre, args.limite)
        if en_batch:
            attendues = mode_batch.pages_en_attente(run)
            pages = [p for p in pages if p.id not in attendues]
        logger.info(
            "run %d — %d page(s) à transcrire (périmètre : %s)",
            run.id,
            len(pages),
            perimetre,
        )
        if not pages and not (en_batch and mode_batch.pages_en_attente(run)):
            logger.info("rien à faire")
            return 0

        t0 = time.time()
        if en_batch:
            echecs = _passe_batch(session, run, backend, pages, dpi, format)
        else:
            echecs = _passe_sequentielle(session, run, backend, pages, dpi, format)
        duree = time.time() - t0

        transcrites = (
            session.execute(
                select(func.count(PageTranscription.id)).where(
                    PageTranscription.run_id == run.id
                )
            ).scalar()
            or 0
        )
        qualite = session.execute(
            select(func.avg(PageTranscription.quality_score)).where(
                PageTranscription.run_id == run.id
            )
        ).scalar()

        logger.info("=== Bilan ===")
        logger.info("  run            : %d (%s)", run.id, run.label)
        logger.info("  transcrites    : %d (run entier)", transcrites)
        logger.info("  échecs         : %d", echecs)
        logger.info(
            "  qualité wordfreq : %.2f", qualite if qualite is not None else 0.0
        )
        logger.info("  durée          : %.0f s", duree)
        if backend.nom == "mistral":
            prix = transcrites * OcrConfig.MISTRAL_PRICE_PER_1000_PAGES.value / 1000
            if en_batch:
                prix /= 2
            logger.info(
                "  coût estimé    : ~%.2f $ (run entier, tarif %s)",
                prix,
                "batch" if en_batch else "standard",
            )

    return 0 if not echecs else 1


def _passe_batch(session, run, backend, pages, dpi, format) -> int:
    """Soumet les pages restantes par lots, puis attend et récolte tout."""
    client = mode_batch.ClientBatch(backend.api_key)
    if pages:
        ouverts = mode_batch.soumettre(
            session, run, client, pages, model=backend.model, dpi=dpi, format=format
        )
        logger.info("%d lot(s) ouvert(s) — attente des résultats", ouverts)
    return mode_batch.attendre(session, run, client)


def _passe_sequentielle(session, run, backend, pages, dpi, format) -> int:
    """Transcrit page à page, en commitant régulièrement."""
    echecs = 0
    for compteur, page in enumerate(tqdm(pages, desc=f"OCR {backend.nom}"), start=1):
        try:
            image = rendre_page(page.pdf_name, page.page_number, dpi, format)
            resultat = backend.transcrire(image, format)
        except (PdfIntrouvable, ErreurOcr, ValueError, OSError) as exc:
            logger.warning(
                "page %d (%s p%d) en échec : %s",
                page.id,
                page.pdf_name,
                page.page_number,
                exc,
            )
            echecs += 1
            continue
        texte = normaliser(resultat.texte)
        enregistrer(
            session,
            run,
            page,
            texte,
            resultat.layout,
            round(wordfreq_quality_score(texte), 3),
        )
        if compteur % OcrConfig.COMMIT_EVERY.value == 0:
            session.commit()
    session.commit()
    return echecs


if __name__ == "__main__":
    sys.exit(main())
