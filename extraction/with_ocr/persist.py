"""Persistance de la passe OCR : un run, des transcriptions page à page.

Le run porte la passe — backend, modèle, DPI, consigne, périmètre : de quoi
la rejouer et la juger. Les transcriptions s'y rattachent ; le squelette
(`page_extraction`) n'est jamais touché. L'unicité (run, page) rend la passe
**reprenable** : après une interruption, relancer avec ``--run-id`` reprend
où elle s'était arrêtée, sans repayer les pages déjà faites.
"""

from sqlalchemy import and_, delete, or_, select, true
from sqlalchemy.orm import Session

from database.models import PageExtraction, PageTranscription, Run
from database.pages import derives
from database.runs import TRANSCRIPTION, creer_run
from extraction.with_ocr.config import OcrConfig

PERIMETRES = ("manuscrit", "typé", "suspect", "tout")
# Pas un périmètre du corpus mais du run : ses pages en dérive, à refaire.
DERIVES = "derives"


def perimetres(perimetre: str) -> list[str]:
    """Les périmètres d'une passe, ``manuscrit+suspect`` compris.

    Raises:
        ValueError: l'un d'eux est inconnu.
    """
    noms = [p.strip() for p in perimetre.split("+")]
    inconnus = [p for p in noms if p not in PERIMETRES]
    if inconnus:
        raise ValueError(
            f"périmètre inconnu : {inconnus[0]!r} (attendu : {', '.join(PERIMETRES)})"
        )
    return noms


def _clause(perimetre: str):
    """Le filtre SQL d'un périmètre simple."""
    if perimetre == "manuscrit":
        return PageExtraction.needs_ocr.is_(True)
    if perimetre == "typé":
        return PageExtraction.needs_ocr.is_(False)
    if perimetre == "suspect":
        return and_(
            PageExtraction.needs_ocr.is_(False),
            PageExtraction.quality_score < OcrConfig.SUSPECT_QUALITY.value,
        )
    return true()


def ouvrir_run(
    session: Session,
    *,
    backend: str,
    model: str,
    dpi: int,
    perimetre: str,
    format: str = "png",
    batch: bool = False,
    prompt: str | None = None,
    label: str | None = None,
    auteur: str | None = None,
    notes: str | None = None,
) -> Run:
    """Ouvre un run de genre ``transcription`` pour la passe.

    Args:
        session: session ouverte sur la base.
        backend: ``mistral`` ou ``ollama``.
        model: modèle employé, tel que nommé par le backend.
        dpi: résolution du rendu des pages.
        perimetre: ce sur quoi la passe tourne (``PERIMETRES``).
        format: ``png`` ou ``jpeg`` — le format de l'image envoyée.
        batch: la passe est passée par l'API batch (mistral), pas page à page.
        prompt: consigne de transcription, pour les backends à prompt.
        label: nom court lisible ; défaut : « OCR <backend> <model> — <périmètre> ».
        auteur: passé à ``creer_run``, qui le résout d'office s'il manque.
        notes: tout ce qui aide à relire la passe plus tard.

    Returns:
        Le run créé, déjà flush (son id est attribué).
    """
    return creer_run(
        session,
        TRANSCRIPTION,
        label=label or f"OCR {backend} {model} — {perimetre}",
        source="extraction/with_ocr",
        model=f"{backend}:{model}",
        parameters={
            "backend": backend,
            "model": model,
            "dpi": dpi,
            "format": format,
            "mode": "batch" if batch else "séquentiel",
            "perimetre": perimetre,
            "prompt": prompt,
        },
        corpus=perimetre,
        author=auteur,
        notes=notes,
    )


def pages_a_transcrire(
    session: Session,
    run: Run,
    perimetre: str,
    limite: int | None = None,
    categorie: str | None = None,
) -> list[PageExtraction]:
    """Les pages du périmètre, sauf celles déjà transcrites dans ce run.

    Args:
        session: session ouverte sur la base.
        run: la passe en cours — ses transcriptions existantes sont exclues.
        perimetre: ``manuscrit`` (pages `needs_ocr`), ``typé``, ``suspect``
            (typé sous le seuil de qualité — les formulaires pré-imprimés
            remplis à la main que `needs_ocr` manque) ou ``tout`` ; ou
            plusieurs joints par ``+`` (``manuscrit+suspect``) : une même
            passe, étendue à un second périmètre.
        limite: nombre maximal de pages, pour un essai.
        categorie: catégorie du versement (`page_extraction.categorie`) ;
            ``None`` ne filtre pas.

    Returns:
        Les pages à traiter, dans l'ordre de leurs ids.

    Raises:
        ValueError: périmètre inconnu.
    """
    clauses = [_clause(p) for p in perimetres(perimetre)]

    deja = select(PageTranscription.page_extraction_id).where(
        PageTranscription.run_id == run.id
    )
    requete = (
        select(PageExtraction)
        .where(PageExtraction.id.not_in(deja), or_(*clauses))
        .order_by(PageExtraction.id)
    )
    if categorie is not None:
        requete = requete.where(PageExtraction.categorie == categorie.upper())
    if limite is not None:
        requete = requete.limit(limite)
    return list(session.scalars(requete))


def enregistrer(
    session: Session,
    run: Run,
    page: PageExtraction,
    texte: str,
    layout: list[dict] | None,
    quality_score: float,
) -> PageTranscription:
    """Ajoute la transcription d'une page au run (sans commiter)."""
    ligne = PageTranscription(
        run_id=run.id,
        page_extraction_id=page.id,
        pdf_name=page.pdf_name,
        page_number=page.page_number,
        text=texte,
        layout=layout,
        quality_score=quality_score,
    )
    session.add(ligne)
    return ligne


def etendre_perimetre(session: Session, run: Run, demande: str | None) -> str:
    """Le périmètre d'une reprise : celui du run, étendu si la commande en
    demande un autre.

    Une même passe — même modèle, mêmes paramètres — peut couvrir le manuscrit
    puis les formulaires « suspects » : c'est une couche, pas deux, et un seul
    run est actif par genre. Le run note l'extension (``manuscrit+suspect``)
    dans ses paramètres et son corpus.

    Returns:
        Le périmètre à parcourir, composite s'il le faut.
    """
    parametres = dict(run.parameters or {})
    actuel = parametres.get("perimetre", "manuscrit")
    if demande is None or demande in perimetres(actuel):
        return actuel
    perimetres(demande)  # valide
    nouveau = f"{actuel}+{demande}"
    run.parameters = {**parametres, "perimetre": nouveau}
    run.corpus = nouveau
    session.flush()
    return nouveau


def pages_en_derive(
    session: Session, run: Run, limite: int | None = None
) -> list[PageExtraction]:
    """Retire du run ses transcriptions en dérive et rend leurs pages, à refaire.

    La dérive (`database.pages.est_derive`) est un accident de tirage du
    modèle : la même page, rejouée, ne dérive en général pas. La passe la
    rejoue donc dans le **même** run — c'est la même couche, le même modèle —
    et le run compte ces reprises dans ses paramètres (``derives_reprises``).

    Returns:
        Les pages dont la transcription vient d'être retirée, dans l'ordre de
        leurs ids, `limite` au plus ; vide si le run n'a pas de dérive.
    """
    ids = [t.page_extraction_id for t in derives(session, run.id)][:limite]
    if not ids:
        return []
    session.execute(
        delete(PageTranscription).where(
            PageTranscription.run_id == run.id,
            PageTranscription.page_extraction_id.in_(ids),
        )
    )
    parametres = dict(run.parameters or {})
    run.parameters = {
        **parametres,
        "derives_reprises": parametres.get("derives_reprises", 0) + len(ids),
    }
    session.flush()
    return list(
        session.scalars(
            select(PageExtraction)
            .where(PageExtraction.id.in_(ids))
            .order_by(PageExtraction.id)
        )
    )


def noter_backend(session: Session, run: Run, backend) -> None:
    """Le run porte les réglages de génération du backend, s'il en a.

    Un run ouvert avant le plafond de tokens (run 18) ne les a pas : la
    reprise les note, comme elle note une extension de périmètre, pour que
    le run dise ce qui a réellement tourné.
    """
    reglages = {
        cle: getattr(backend, cle)
        for cle in ("num_predict",)
        if getattr(backend, cle, None) is not None
    }
    if getattr(backend, "retirable", False):
        reglages["retirages"] = OcrConfig.OLLAMA_RETIRAGES.value
    parametres = dict(run.parameters or {})
    if reglages and any(parametres.get(k) != v for k, v in reglages.items()):
        run.parameters = {**parametres, **reglages}
        session.flush()
