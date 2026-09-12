"""Mesurer la fidélité d'un backend OCR là où une vérité existe : le typé.

Il n'y a pas d'étalon manuscrit — personne n'a encore transcrit à la main un
échantillon de pages. Ce module mesure ce qui peut l'être aujourd'hui : sur
des pages **typées** dont la couche texte du PDF est bonne (score wordfreq
élevé), on fait transcrire l'image par le backend et on compare au texte de
la couche, caractère à caractère (CER) et mot à mot (WER). C'est une mesure
du modèle, de la consigne et de la normalisation sur de l'imprimé — pas de
la lecture du manuscrit, qui reste à mesurer sur un étalon annoté. Le
retirage des dérives est celui de la passe (`transcrire_propre`) : on
mesure ce que la passe aurait gardé.

    uv run python -m extraction.with_ocr.fidelite --backend ollama --model ornith-1.5:9b --taille 30

Rien n'est persisté : ni le texte, ni les images. Seuls les scores s'affichent.
"""

import argparse
import random
import re
import sys
import unicodedata
from dataclasses import dataclass

from rapidfuzz.distance import Levenshtein
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.db import check_connection, get_engine
from database.models import PageExtraction
from extraction.with_ocr.backends import ErreurOcr, fabrique_backend, transcrire_propre
from extraction.with_ocr.config import OcrConfig
from extraction.with_ocr.render import PdfIntrouvable, rendre_page

# Une page typée sert de vérité si sa couche texte est bonne et de taille de
# page : trop courte, la mesure est bruitée ; trop longue, c'est une annexe.
QUALITE_MIN = 0.9
CARACTERES_MIN = 800
CARACTERES_MAX = 4000
GRAINE = 2019


@dataclass
class Score:
    page_id: int
    pdf_name: str
    page_number: int
    caracteres: int
    rapport: float  # longueur de l'hypothèse sur celle de la référence
    cer: float
    wer: float
    cer_plie: float
    plafonne: bool


def plier(texte: str) -> str:
    """Le texte réduit à ce que l'OCR ne peut pas confondre avec du style :
    espaces normalisés, une ligne."""
    texte = unicodedata.normalize("NFC", texte)
    return re.sub(r"\s+", " ", texte).strip()


def plier_fort(texte: str) -> str:
    """Comme `plier`, puis sans accents, sans casse, sans ponctuation : ce qui
    reste est le contenu ; la différence avec `plier` mesure l'orthographe."""
    texte = unicodedata.normalize("NFD", plier(texte).lower())
    texte = "".join(c for c in texte if unicodedata.category(c)[0] in "LNZ")
    return re.sub(r"\s+", " ", texte).strip()


def cer(reference: str, hypothese: str) -> float:
    """Distance de Levenshtein en caractères, rapportée à la référence."""
    reference, hypothese = plier(reference), plier(hypothese)
    if not reference:
        return 0.0 if not hypothese else 1.0
    return Levenshtein.distance(reference, hypothese) / len(reference)


def wer(reference: str, hypothese: str) -> float:
    """Distance de Levenshtein en mots, rapportée à la référence."""
    ref, hyp = plier(reference).split(), plier(hypothese).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return Levenshtein.distance(ref, hyp) / len(ref)


def cer_plie(reference: str, hypothese: str) -> float:
    """CER sur le contenu seul (accents, casse et ponctuation retirés)."""
    return cer(plier_fort(reference), plier_fort(hypothese))


def tirer(session: Session, taille: int, graine: int = GRAINE) -> list[PageExtraction]:
    """`taille` pages typées de bonne couche texte, à parts égales entre
    départements, tirage reproductible."""
    candidates = list(
        session.scalars(
            select(PageExtraction)
            .where(
                PageExtraction.needs_ocr.is_(False),
                PageExtraction.quality_score >= QUALITE_MIN,
                func.length(PageExtraction.text).between(CARACTERES_MIN, CARACTERES_MAX),
            )
            .order_by(PageExtraction.id)
        )
    )
    par_departement: dict[str, list[PageExtraction]] = {}
    for page in candidates:
        par_departement.setdefault((page.pdf_name or "")[3:5], []).append(page)
    alea = random.Random(graine)
    tirage: list[PageExtraction] = []
    for pages in par_departement.values():
        tirage.extend(alea.sample(pages, min(len(pages), taille // len(par_departement))))
    return tirage


def mesurer(backend, page: PageExtraction, dpi: int, format: str) -> Score:
    image = rendre_page(page.pdf_name, page.page_number, dpi, format)
    hypothese, resultat, _ = transcrire_propre(backend, image, format)
    reference = page.text or ""
    longueur = len(plier(reference))
    return Score(
        page.id,
        page.pdf_name,
        page.page_number,
        longueur,
        len(plier(hypothese)) / longueur if longueur else 0.0,
        cer(reference, hypothese),
        wer(reference, hypothese),
        cer_plie(reference, hypothese),
        resultat.plafonne,
    )


def _moyenne(valeurs: list[float]) -> float:
    return sum(valeurs) / len(valeurs) if valeurs else 0.0


def _mediane(valeurs: list[float]) -> float:
    if not valeurs:
        return 0.0
    v = sorted(valeurs)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--backend", choices=("mistral", "ollama"), default="ollama")
    p.add_argument("--model", default=None)
    p.add_argument("--taille", type=int, default=30, help="pages tirées (défaut : 30)")
    p.add_argument("--graine", type=int, default=GRAINE)
    p.add_argument(
        "--pages", default=None, help="ids de page_extraction, séparés par des virgules, au lieu du tirage"
    )
    p.add_argument("--dpi", type=int, default=OcrConfig.DPI.value)
    p.add_argument("--format", choices=("png", "jpeg"), default="jpeg")
    args = p.parse_args(argv)

    engine = get_engine()
    check_connection(engine)
    backend = fabrique_backend(args.backend, args.model)
    scores: list[Score] = []
    with Session(engine) as session:
        if args.pages:
            ids = [int(i) for i in args.pages.split(",")]
            pages = list(session.scalars(select(PageExtraction).where(PageExtraction.id.in_(ids))))
        else:
            pages = tirer(session, args.taille, args.graine)
        print(f"{len(pages)} page(s) typée(s) tirée(s) (graine {args.graine}) · {backend.nom}:{backend.model}")
        print(f"{'page':>6} {'cahier':36} {'p':>3} {'car.':>5} {'long.':>5} {'CER':>6} {'WER':>6} {'CER plié':>8}")
        for page in pages:
            try:
                s = mesurer(backend, page, args.dpi, args.format)
            except (PdfIntrouvable, ErreurOcr, ValueError, OSError) as exc:
                print(f"{page.id:>6} {page.pdf_name[:36]:36} {page.page_number:>3} en échec : {exc}", file=sys.stderr)
                continue
            scores.append(s)
            print(
                f"{s.page_id:>6} {s.pdf_name[:36]:36} {s.page_number:>3} {s.caracteres:>5} "
                f"{s.rapport:5.2f} {s.cer:6.3f} {s.wer:6.3f} {s.cer_plie:8.3f}"
                + (" plafonné" if s.plafonne else ""),
                flush=True,
            )

    if not scores:
        return 1
    for nom, cle in (("CER", "cer"), ("WER", "wer"), ("CER plié", "cer_plie")):
        v = [getattr(s, cle) for s in scores]
        print(f"{nom:9}: moyenne {_moyenne(v):.3f} · médiane {_mediane(v):.3f} · max {max(v):.3f}")
    total = sum(s.caracteres for s in scores)
    pondere = sum(s.cer * s.caracteres for s in scores) / total
    print(f"CER pondéré par la longueur : {pondere:.3f} sur {total} caractères, {len(scores)} page(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
