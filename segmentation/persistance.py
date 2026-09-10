"""Lecture des pages, écriture des doléances découpées.

Le découpage lui-même est dans `decoupage.py` et ne connaît pas la base ; ce
module fait la navette entre les deux tables.

Le regroupement se fait par **cahier** (`page_extraction.pdf_name`), pas par
contribution : le pipeline `extraction/without_ocr` crée une contribution par
page, une doléance qui court sur deux pages en traverserait donc deux. Le cahier
est la seule unité qui contient sûrement la doléance entière.
"""

from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from database.models import Doleance as LigneDoleance
from database.models import PageExtraction
from segmentation.decoupage import Doleance, decouper_cahier


def lire_pages(session: Session, garder_pages_ocr: bool = False) -> list[PageExtraction]:
    """Lit les pages extraites, triées par cahier puis par page.

    Les pages `needs_ocr` sont écartées par défaut, comme dans
    `database/export_dataset.py` : leur texte est du bruit d'extraction, il
    ferait déclencher les règles de découpage au hasard.

    Args:
        session: session ouverte sur la base.
        garder_pages_ocr: inclure aussi les pages manuscrites.

    Returns:
        Les pages dans l'ordre de lecture des cahiers.
    """
    requete = select(PageExtraction).order_by(
        PageExtraction.pdf_name, PageExtraction.page_number
    )
    if not garder_pages_ocr:
        requete = requete.where(PageExtraction.needs_ocr.is_not(True))
    return list(session.scalars(requete))


def grouper_par_cahier(pages: list[PageExtraction]) -> dict[str, list[PageExtraction]]:
    """Regroupe les pages par PDF, en conservant leur ordre.

    Les pages sans `pdf_name` sont écartées : la colonne est nullable, et sans
    elle on ne sait pas de quel cahier vient la page — la rattacher au hasard
    fabriquerait des doléances à cheval sur deux communes.

    Args:
        pages: pages triées (``lire_pages``).

    Returns:
        ``{pdf_name: pages du cahier}``.
    """
    cahiers: dict[str, list[PageExtraction]] = defaultdict(list)
    for page in pages:
        if page.pdf_name:
            cahiers[page.pdf_name].append(page)
    return dict(cahiers)


def decouper_pages(pages: list[PageExtraction]) -> list[Doleance]:
    """Découpe les pages d'un cahier en doléances."""
    return decouper_cahier([(p.page_number, p.text or "") for p in pages])


def cahiers_deja_decoupes(session: Session) -> set[str]:
    """Noms des PDF ayant déjà des doléances en base."""
    return set(session.scalars(select(LigneDoleance.pdf_name).distinct()))


def oublier_cahier(session: Session, pdf_name: str) -> None:
    """Supprime les doléances d'un cahier, pour le redécouper."""
    session.execute(delete(LigneDoleance).where(LigneDoleance.pdf_name == pdf_name))


def enregistrer_cahier(
    session: Session, pdf_name: str, pages: list[PageExtraction]
) -> list[LigneDoleance]:
    """Découpe un cahier et ajoute ses doléances à la session (sans commit).

    Args:
        session: session ouverte sur la base.
        pdf_name: nom du PDF découpé.
        pages: ses pages, dans l'ordre.

    Returns:
        Les lignes ajoutées, dans l'ordre du cahier.
    """
    contribution_par_page = {p.page_number: p.contribution_id for p in pages}
    ville = next((p.city for p in pages if p.city), None)

    lignes = []
    for rang, doleance in enumerate(decouper_pages(pages)):
        ligne = LigneDoleance(
            contribution_id=contribution_par_page.get(doleance.page_debut),
            pdf_name=pdf_name,
            city=ville,
            position=rang,
            start_page=doleance.page_debut,
            end_page=doleance.page_fin,
            text=doleance.texte,
            signal=doleance.signal,
            num_words=len(doleance.texte.split()),
        )
        session.add(ligne)
        lignes.append(ligne)
    return lignes
