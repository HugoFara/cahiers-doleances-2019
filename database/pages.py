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


# Sur certaines pages, le modèle ne s'arrête plus : il recopie la même ligne
# des milliers de fois, ou dérive en variations jusqu'à la limite de
# génération. Mesuré sur ornith-1.5 (run 18, 2026-09-12) : 11 pages sur
# 2 550, de 17 000 à 50 000 caractères, jusqu'à 8 000 mots — une page
# manuscrite n'en porte pas 500. Le score wordfreq ne les voit pas : répéter
# des mots français ne le fait pas baisser. Quatre signes, dont un suffit ;
# les seuils laissent passer les 2 539 autres pages (ratios à 1,0 sauf
# trois pages entre 0,77 et 0,93, toutes courtes).
MAX_MOTS_PAGE = 2_000          # une page A4 dense tapée en fait moins de 1 000
MAX_CARACTERES_PAGE = 12_000
MOTS_POUR_RATIO = 100          # en dessous, le ratio de n-grammes ne veut rien dire
LARGEUR_NGRAMME = 8
RATIO_NGRAMMES_MIN = 0.5       # part de n-grammes distincts sous laquelle ça boucle
LIGNES_POUR_RATIO = 50
RATIO_LIGNES_MIN = 0.2

_MOT = re.compile(r"\w+")


def est_derive(texte: str) -> bool:
    """Le texte est-il une dérive du modèle — boucle ou emballement ?

    Args:
        texte: la transcription d'une page.

    Returns:
        Vrai si la page est trop longue pour une page, ou si ses mots ou ses
        lignes se répètent au point de ne plus rien dire.
    """
    if len(texte) > MAX_CARACTERES_PAGE:
        return True
    mots = _MOT.findall(texte.lower())
    if len(mots) > MAX_MOTS_PAGE:
        return True
    if len(mots) >= MOTS_POUR_RATIO:
        n = LARGEUR_NGRAMME
        grammes = [tuple(mots[i : i + n]) for i in range(len(mots) - n + 1)]
        if len(set(grammes)) / len(grammes) < RATIO_NGRAMMES_MIN:
            return True
    lignes = [ligne.strip() for ligne in texte.split("\n") if ligne.strip()]
    if len(lignes) >= LIGNES_POUR_RATIO and len(set(lignes)) / len(lignes) < RATIO_LIGNES_MIN:
        return True
    return False


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
        # un commentaire ou une dérive ne sont pas une lecture de la page :
        # la page reste « transcrite » (on ne retombe pas sur le squelette,
        # qui est du bruit sur un manuscrit), mais on n'en lit rien
        if est_commentaire_page_vide(texte) or est_derive(texte):
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


def derives(session: Session, run_id: int | None = None) -> list[PageTranscription]:
    """Les transcriptions d'un run (l'actif par défaut) que `est_derive` écarte.

    C'est la liste à repasser avec un autre modèle ou un plafond de génération.
    """
    if run_id is None:
        run = run_actif(session, TRANSCRIPTION)
        if run is None:
            return []
        run_id = run.id
    lignes = session.scalars(
        select(PageTranscription)
        .where(PageTranscription.run_id == run_id)
        .order_by(PageTranscription.pdf_name, PageTranscription.page_number)
    )
    return [t for t in lignes if est_derive(t.text or "")]
