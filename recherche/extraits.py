"""Fabrique l'extrait montré pour un résultat de recherche.

Deux contraintes se croisent ici, et l'ordre dans lequel on les traite décide de
la justesse du résultat.

**Le caviardage d'abord, l'extrait ensuite.** Les passages personnels sont des
offsets dans le texte d'origine (`pii_span`) : les appliquer après avoir découpé
une fenêtre les décalerait. On caviarde donc le texte entier, puis on y cherche
le terme. Conséquence assumée : un terme qui ne se trouvait que dans un passage
occulté disparaît de l'extrait, et le résultat s'ouvre alors sur le début du
texte. C'est le bon sens de l'erreur — la recherche est le premier endroit où le
corpus se lit en vrac, hors du contexte d'un cahier.

**PostgreSQL radicalise, Python non.** `to_tsvector` ramène « éoliennes »,
« éolienne » et « éolien » au même lexème ; retrouver le mot dans le texte
demande donc de raccourcir le terme cherché jusqu'à ce qu'il morde. D'où les
préfixes dégressifs, bornés par `PREFIXE_MIN`.

Module sans base de données : il ne manipule que des chaînes, et se teste tel
quel.
"""

import re
import unicodedata

from recherche.config import FENETRE, MARGE_BORD, PREFIXE_MIN

# Opérateurs de `websearch_to_tsquery` : ils ne sont pas des mots à surligner.
_OPERATEURS = frozenset({"or", "ou", "and", "et"})
_MOT = re.compile(r"[^\W\d_]+", re.UNICODE)


def plier(texte: str) -> str:
    """Minuscules sans accents — la même indifférence que la configuration SQL."""
    decompose = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def termes(requete: str) -> list[str]:
    """Les mots d'une requête qu'il y a lieu de retrouver dans le texte.

    Écarte ce que `websearch_to_tsquery` traite comme syntaxe : les mots niés
    par un tiret — les montrer serait exactement contraire à la demande — et les
    opérateurs booléens.

    Args:
        requete: la requête telle que tapée.

    Returns:
        Les termes pliés, sans doublon, dans l'ordre.
    """
    trouves: list[str] = []
    for brut in requete.replace('"', " ").split():
        if brut.startswith("-"):
            continue
        for mot in _MOT.findall(plier(brut)):
            if mot not in _OPERATEURS and mot not in trouves:
                trouves.append(mot)
    return trouves


def _position(plie: str, terme: str) -> int:
    """Où commence le premier mot du texte qui ressemble à ce terme.

    Raccourcit le terme tant qu'il ne mord pas, jusqu'à `PREFIXE_MIN`.

    Returns:
        L'indice du début du mot, ou -1.
    """
    for taille in range(len(terme), PREFIXE_MIN - 1, -1):
        motif = re.compile(r"\b" + re.escape(terme[:taille]))
        trouve = motif.search(plie)
        if trouve:
            return trouve.start()
    return -1


def _bord(texte: str, indice: int, vers_la_droite: bool, marge: int = MARGE_BORD) -> int:
    """Recule ou avance jusqu'à une frontière de mot, sans aller trop loin.

    La marge n'est pas une précaution théorique : l'OCR produit des blocs de
    centaines de caractères sans espace, et chercher une frontière sans borne y
    remonterait jusqu'au début du texte — l'extrait ne contiendrait alors plus
    le terme cherché. Passé la marge, on coupe dans le mot ; les points de
    suspension disent déjà qu'on a coupé.
    """
    depart = indice
    if vers_la_droite:
        while indice < len(texte) and not texte[indice].isspace():
            indice += 1
        return indice if indice - depart <= marge else depart
    while indice > 0 and not texte[indice - 1].isspace():
        indice -= 1
    return indice if depart - indice <= marge else depart


def fenetre(texte: str, mots: list[str], largeur: int = FENETRE) -> str:
    """Un extrait centré sur le premier terme trouvé, coupé aux mots.

    Args:
        texte: le texte à extraire, **déjà caviardé** le cas échéant.
        mots: les termes pliés, tels que rendus par `termes`.
        largeur: nombre de caractères visés.

    Returns:
        L'extrait, encadré de points de suspension quand il ne touche pas les
        bords du texte. Vide si le texte l'est.
    """
    propre = " ".join(texte.split())
    if not propre:
        return ""
    if len(propre) <= largeur:
        return propre

    plie = plier(propre)
    trouve = min((p for p in (_position(plie, m) for m in mots) if p >= 0), default=-1)
    # Aucun terme retrouvé — le mot était dans un passage occulté, ou la
    # radicalisation a trop éloigné la forme : on ouvre sur le début du texte.
    centre = trouve if trouve >= 0 else 0

    debut = _bord(propre, max(0, centre - largeur // 3), vers_la_droite=False)
    # La fin doit dépasser le terme, pas seulement la largeur demandée : quand
    # le début a reculé jusqu'au bord du texte, `debut + largeur` peut retomber
    # avant le mot trouvé, et l'extrait ne le montrerait pas.
    visee = max(debut + largeur, centre + largeur - largeur // 3)
    fin = _bord(propre, min(len(propre), visee), vers_la_droite=True)
    return ("… " if debut > 0 else "") + propre[debut:fin] + (" …" if fin < len(propre) else "")
