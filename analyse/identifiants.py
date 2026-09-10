"""Format des identifiants de document échangés avec l'équipe analyse.

`export_dataset.py` écrit l'id, `load_analysis.py` le relit : les deux doivent
s'accorder, et rien ne le garantit s'ils codent chacun leur convention.

Le corpus s'exporte à deux niveaux — la contribution (une page, historique) ou
la doléance (le texte d'un contributeur). Les deux tables ont des id
auto-incrémentés qui se recouvrent : sans marquage, une livraison sur les
doléances serait rechargée en désignant des contributions au hasard. D'où le
préfixe, porté par le seul niveau introduit après coup, pour que les livraisons
déjà faites restent relisibles telles quelles.
"""

CONTRIBUTION = "contribution"
DOLEANCE = "doleance"
NIVEAUX = (CONTRIBUTION, DOLEANCE)

PREFIXE_DOLEANCE = "d"


def id_document(niveau: str, identifiant: int) -> str:
    """Identifiant de document à écrire dans le CSV d'entrée de l'analyse.

    Args:
        niveau: ``CONTRIBUTION`` ou ``DOLEANCE``.
        identifiant: la clé primaire de la ligne exportée.

    Returns:
        L'id textuel, préfixé si le niveau l'exige.

    Raises:
        ValueError: si le niveau est inconnu.
    """
    if niveau == CONTRIBUTION:
        return str(identifiant)
    if niveau == DOLEANCE:
        return f"{PREFIXE_DOLEANCE}{identifiant}"
    raise ValueError(f"niveau inconnu : {niveau!r} (attendu : {', '.join(NIVEAUX)})")


def lire_id_document(brut: str) -> tuple[str, int] | None:
    """Relit un identifiant de document renvoyé par l'analyse.

    Args:
        brut: l'id tel qu'il figure dans `instances.json`.

    Returns:
        Le couple (niveau, identifiant), ou ``None`` si l'id n'est pas
        interprétable — les livraisons antérieures numérotent parfois leurs
        documents autrement.
    """
    if brut is None:
        return None
    texte = str(brut).strip()
    niveau = CONTRIBUTION
    if texte[:1].lower() == PREFIXE_DOLEANCE:
        niveau, texte = DOLEANCE, texte[1:]
    try:
        return niveau, int(texte)
    except (TypeError, ValueError):
        return None
