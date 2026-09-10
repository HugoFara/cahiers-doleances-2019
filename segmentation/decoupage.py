"""Découpage du texte d'un cahier en doléances, sans base de données.

Le module travaille sur des lignes numérotées par page, ce qui le rend testable
sur des chaînes littérales — comme `insee/communes.py`, et pour la même
raison : la logique intéressante n'a pas besoin de PostgreSQL pour être vérifiée.

**Invariant** : le découpage partitionne les lignes, il n'en supprime aucune.
Recoller les doléances dans l'ordre redonne exactement le texte d'entrée. C'est
ce qui permet de rejouer un découpage plus fin plus tard sans avoir perdu de
texte au passage, et c'est vérifié par un test.
"""

from dataclasses import dataclass

from segmentation import config


@dataclass(frozen=True)
class Ligne:
    """Une ligne de texte et la page dont elle vient."""

    texte: str
    page: int


@dataclass(frozen=True)
class Doleance:
    """Un bloc de lignes consécutives attribué à un même contributeur."""

    texte: str
    page_debut: int
    page_fin: int
    signal: str  # règle qui a ouvert le bloc ; "debut" pour le premier


def lignes_du_cahier(pages: list[tuple[int, str]]) -> list[Ligne]:
    """Aplatit les pages d'un cahier en lignes, en gardant le numéro de page.

    Args:
        pages: couples (numéro de page, texte de la page), dans l'ordre.

    Returns:
        La liste des lignes non vides du cahier.
    """
    lignes: list[Ligne] = []
    for numero, texte in pages:
        for brute in (texte or "").split("\n"):
            if brute.strip():
                lignes.append(Ligne(texte=brute.strip(), page=numero))
    return lignes


def signal_ouverture(ligne: str) -> str | None:
    """Nomme la règle par laquelle cette ligne ouvre une nouvelle doléance.

    Args:
        ligne: la ligne à examiner, déjà détourée.

    Returns:
        Le nom de la règle, ou ``None`` si la ligne n'ouvre rien.
    """
    if config.SEPARATEUR.match(ligne):
        return "separateur"
    if config.NUMEROTATION.match(ligne):
        return "numerotation"
    if config.DATE.match(ligne) or config.DATE_NUMERIQUE.match(ligne):
        return "date"
    if config.APOSTROPHE.match(ligne):
        return "apostrophe"
    return None


def est_cloture(ligne: str) -> bool:
    """Vrai si la ligne contient une formule de politesse finale."""
    return config.CLOTURE.search(ligne) is not None


def est_ligne_de_signature(ligne: str) -> bool:
    """Vrai si la ligne a la forme d'une signature (nom, qualité, ville)."""
    return len(ligne) <= config.LONGUEUR_LIGNE_SIGNATURE


def _assembler(lignes: list[Ligne], signal: str) -> Doleance:
    """Construit une doléance à partir de ses lignes."""
    return Doleance(
        texte="\n".join(ligne.texte for ligne in lignes),
        page_debut=lignes[0].page,
        page_fin=lignes[-1].page,
        signal=signal,
    )


def _coupures(lignes: list[Ligne]) -> list[tuple[int, str]]:
    """Repère les indices de ligne où une nouvelle doléance commence.

    Deux mécanismes concourent :

    - un **signal d'ouverture** (date, apostrophe, filet, numérotation) coupe
      avant la ligne, à condition que la doléance en cours pèse déjà
      ``MIN_CARACTERES_DOLEANCE`` — sinon l'en-tête d'une lettre, qui enchaîne
      date et apostrophe, se découperait lui-même ;
    - une **formule de clôture** ferme la doléance après la signature qui la
      suit, ce qui rattrape les contributions qui s'enchaînent sans en-tête.

    Args:
        lignes: les lignes du cahier, dans l'ordre.

    Returns:
        Les couples (indice de ligne, nom de la règle), indices croissants.
    """
    coupures: list[tuple[int, str]] = []
    taille = 0  # caractères accumulés depuis la dernière coupure
    signature_restante: int | None = None  # lignes encore tolérées après clôture

    for i, ligne in enumerate(lignes):
        if i > 0:
            signal = signal_ouverture(ligne.texte)
            if signal is not None and taille >= config.MIN_CARACTERES_DOLEANCE:
                coupures.append((i, signal))
                taille = 0
                signature_restante = None
            elif signature_restante is not None and (
                signature_restante == 0 or not est_ligne_de_signature(ligne.texte)
            ):
                coupures.append((i, "cloture"))
                taille = 0
                signature_restante = None

        taille += len(ligne.texte)
        if signature_restante is not None:
            signature_restante -= 1
        if est_cloture(ligne.texte):
            signature_restante = config.LIGNES_SIGNATURE

    return coupures


def decouper(lignes: list[Ligne]) -> list[Doleance]:
    """Découpe les lignes d'un cahier en doléances.

    Args:
        lignes: les lignes du cahier, dans l'ordre (``lignes_du_cahier``).

    Returns:
        Les doléances dans l'ordre du cahier. Liste vide si aucune ligne.
    """
    if not lignes:
        return []

    coupures = _coupures(lignes)
    debuts = [(0, "debut")] + coupures
    fins = [indice for indice, _ in coupures] + [len(lignes)]

    return [
        _assembler(lignes[debut:fin], signal)
        for (debut, signal), fin in zip(debuts, fins)
        if lignes[debut:fin]
    ]


def decouper_cahier(pages: list[tuple[int, str]]) -> list[Doleance]:
    """Raccourci : des pages d'un cahier aux doléances qu'elles contiennent."""
    return decouper(lignes_du_cahier(pages))
