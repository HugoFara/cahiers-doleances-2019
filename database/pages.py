"""Le texte de lecture d'une page : squelette ou transcription, jamais les deux.

`page_extraction.text` est la couche texte des PDF : elle donne les cahiers
dactylographiés et du bruit sur les manuscrits (`needs_ocr`). Les
transcriptions OCR (`page_transcription`) sont une lecture de l'image,
versionnée par un run de genre `transcription`. Rien n'est écrasé : c'est à la
lecture que l'on choisit, page par page, ce que l'on lit —

1. la transcription du run `transcription` **actif**, si la page en a une ;
2. sinon le squelette, si la page n'est pas `needs_ocr` ;
3. sinon rien : la page n'a pas de texte lisible.

Tout ce qui lit le corpus — segmentation, export vers l'analyse, couverture,
app — passe par ``lire_pages`` et voit le même texte. Activer un autre run de
transcription change la lecture de tout le monde d'un coup, et la désactiver
ramène au squelette seul.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import PageExtraction, PageTranscription
from database.runs import TRANSCRIPTION, run_actif

SQUELETTE = "squelette"
TRANSCRIPTION_ACTIVE = "transcription"
AUCUNE = "aucune"

# Sur une page vide, un modèle de vision-langage écrit une phrase au lieu de
# rien — « Cette image ne contient aucun texte », « La page est vierge »… —
# malgré la consigne (mesuré sur ornith-1.5, 2026-09-11). On ne la lit pas :
# ce serait une doléance de plus, et un commentaire du modèle dans le corpus.
# La règle ne joue que sur un texte court : une vraie contribution qui parle
# d'une page vide n'est pas concernée.
COMMENTAIRE_PAGE_VIDE = re.compile(
    r"\b(?:image|page|document|scan)\b[^.\n]{0,80}"
    r"\b(?:aucun texte|pas de texte|sans (?:texte|écriture)|vide|vierge|blanche)\b",
    re.IGNORECASE,
)
LONGUEUR_COMMENTAIRE = 300


def est_commentaire_page_vide(texte: str) -> bool:
    """Le texte est-il un commentaire de modèle sur une page vide ?"""
    return len(texte) <= LONGUEUR_COMMENTAIRE and bool(
        COMMENTAIRE_PAGE_VIDE.search(texte)
    )


@dataclass
class PageLue:
    """Une page et le texte qu'on en lit.

    Attributes:
        page: la ligne `page_extraction` — cahier, numéro, commune, contribution.
        texte: le texte de lecture, vide si la page n'en a pas.
        source: ``squelette``, ``transcription`` ou ``aucune``.
        transcription: la ligne `page_transcription` lue, s'il y en a une.
    """

    page: PageExtraction
    texte: str
    source: str
    transcription: PageTranscription | None = None

    @property
    def lisible(self) -> bool:
        return self.source != AUCUNE


def transcriptions_actives(session: Session) -> dict[int, PageTranscription]:
    """Les transcriptions du run `transcription` actif, par id de page."""
    run = run_actif(session, TRANSCRIPTION)
    if run is None:
        return {}
    lignes = session.scalars(
        select(PageTranscription).where(PageTranscription.run_id == run.id)
    )
    return {t.page_extraction_id: t for t in lignes}


def lire_page(page: PageExtraction, transcription: PageTranscription | None) -> PageLue:
    """Choisit le texte d'une page : transcription, squelette, ou rien."""
    if transcription is not None:
        texte = transcription.text or ""
        if est_commentaire_page_vide(texte):
            texte = ""
        return PageLue(page, texte, TRANSCRIPTION_ACTIVE, transcription)
    if page.needs_ocr is not True:
        return PageLue(page, page.text or "", SQUELETTE)
    return PageLue(page, "", AUCUNE)


def lire_pages(
    session: Session,
    *,
    garder_illisibles: bool = False,
    ordre: str = "cahier",
    contributions: Iterable[int] | None = None,
) -> list[PageLue]:
    """Les pages du corpus avec leur texte de lecture.

    Args:
        session: session ouverte sur la base.
        garder_illisibles: inclure les pages sans texte (source ``aucune``).
            Par défaut elles sont écartées, comme l'étaient les `needs_ocr`.
        ordre: ``cahier`` (nom du PDF puis page) ou ``contribution``
            (contribution puis page — l'ordre de l'export vers l'analyse).
        contributions: restreindre à ces contributions ; tout le corpus sinon.

    Returns:
        Les pages, dans l'ordre demandé.
    """
    if ordre == "cahier":
        tri = (PageExtraction.pdf_name, PageExtraction.page_number)
    elif ordre == "contribution":
        tri = (PageExtraction.contribution_id, PageExtraction.page_number)
    else:
        raise ValueError(f"ordre inconnu : {ordre!r} (cahier | contribution)")
    requete = select(PageExtraction).order_by(*tri)
    if contributions is not None:
        requete = requete.where(PageExtraction.contribution_id.in_(list(contributions)))
    transcriptions = transcriptions_actives(session)
    lues = [
        lire_page(page, transcriptions.get(page.id))
        for page in session.scalars(requete)
    ]
    if not garder_illisibles:
        lues = [p for p in lues if p.lisible]
    return lues
